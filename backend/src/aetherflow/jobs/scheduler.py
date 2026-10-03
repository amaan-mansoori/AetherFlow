"""Durable one-shot schedule activation through PostgreSQL and the outbox."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from aetherflow.infrastructure.database.models import (
    Job,
    JobEvent,
    JobState,
    OutboxDispatch,
    utc_now,
)
from aetherflow.jobs.state_machine import validate_transition
from aetherflow.observability.metrics import METRICS


@dataclass(frozen=True)
class ScheduledActivation:
    """One durable scheduling decision."""

    job_id: UUID
    job_version: int


class DurableScheduler:
    """Activate due jobs in short PostgreSQL transactions.

    Row locks coordinate concurrent PostgreSQL schedulers. SQLite ignores
    ``FOR UPDATE``; its tests therefore validate deterministic behavior only.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        scheduler_id: str,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        if not scheduler_id:
            raise ValueError("scheduler_id must not be blank")
        self._session_factory = session_factory
        self._scheduler_id = scheduler_id
        self._now = now

    async def poll_once(self, limit: int = 100) -> list[ScheduledActivation]:
        if limit < 1:
            raise ValueError("limit must be positive")
        METRICS.inc("aetherflow_scheduler_poll_cycles_total")
        activations: list[ScheduledActivation] = []
        for _ in range(limit):
            activation = await self._activate_one()
            if activation is None:
                break
            activations.append(activation)
        return activations

    async def _activate_one(self) -> ScheduledActivation | None:
        now = self._now()
        async with self._session_factory() as session:
            job = await session.scalar(
                select(Job)
                .options(selectinload(Job.attempts), selectinload(Job.result))
                .where(
                    Job.state == JobState.ACCEPTED,
                    Job.schedule_at.is_not(None),
                    Job.schedule_at <= now,
                )
                .order_by(Job.schedule_at.asc(), Job.created_at.asc(), Job.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None

            validate_transition(job.state, JobState.QUEUED)
            next_version = job.version + 1
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(Job)
                    .where(
                        Job.id == job.id,
                        Job.state == JobState.ACCEPTED,
                        Job.version == job.version,
                    )
                    .values(
                        state=JobState.QUEUED,
                        version=next_version,
                        updated_at=now,
                    )
                ),
            )
            if result.rowcount != 1:
                await session.rollback()
                METRICS.inc("aetherflow_scheduler_claim_conflicts_total")
                return None

            session.add(
                JobEvent(
                    job_id=job.id,
                    event_type="SCHEDULED_JOB_ACTIVATED",
                    prior_state=JobState.ACCEPTED,
                    next_state=JobState.QUEUED,
                    actor=f"scheduler:{self._scheduler_id}",
                    payload={
                        "reason": "schedule_due",
                        "schedule_at": job.schedule_at.isoformat()
                        if job.schedule_at is not None
                        else None,
                    },
                )
            )
            session.add(
                OutboxDispatch(
                    job_id=job.id,
                    job_version=next_version,
                    enqueued_at=now,
                    message_type="JOB_DISPATCH",
                    schema_version="v1",
                )
            )
            await session.commit()

        METRICS.inc("aetherflow_scheduler_claims_total")
        METRICS.inc("aetherflow_scheduled_jobs_due_total")
        scheduled_at = job.schedule_at or now
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=UTC)
        comparison_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
        METRICS.observe(
            "aetherflow_scheduler_lag_seconds",
            max(0.0, (comparison_now - scheduled_at).total_seconds()),
        )
        METRICS.inc("aetherflow_outbox_records_created_total")
        return ScheduledActivation(job.id, next_version)
