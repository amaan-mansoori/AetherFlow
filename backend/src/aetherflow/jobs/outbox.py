"""Transactional outbox publication and recovery boundary."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aetherflow.infrastructure.database.models import OutboxDispatch, utc_now
from aetherflow.jobs.dispatch import DispatchFailure, DispatchMessage, JobDispatcher


@dataclass(frozen=True)
class OutboxPublication:
    """Result of one outbox publication attempt."""

    outbox_id: UUID
    job_id: UUID
    published: bool


class OutboxPublisher:
    """Claim outbox rows briefly, publish outside DB transactions, then finalize."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dispatcher: JobDispatcher,
        *,
        publisher_id: str | None = None,
        lease_seconds: int = 60,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._publisher_id = publisher_id or str(uuid4())
        self._lease_seconds = lease_seconds

    async def publish_once(self) -> OutboxPublication | None:
        claimed = await self._claim_one()
        if claimed is None:
            return None
        if claimed.message_type != "JOB_DISPATCH" or claimed.schema_version != "v1":
            error = "Unsupported outbox dispatch type or schema."
            await self._record_failure(claimed.id, error)
            raise DispatchFailure(error)
        message = DispatchMessage(
            job_id=claimed.job_id,
            job_version=claimed.job_version,
            enqueued_at=claimed.enqueued_at,
            schema_version=claimed.schema_version,
        )
        try:
            await self._dispatcher.dispatch(message)
        except Exception as exc:
            await self._record_failure(claimed.id, str(exc))
            if isinstance(exc, DispatchFailure):
                raise
            raise DispatchFailure("Outbox dispatch failed.") from exc
        await self._mark_published(claimed.id)
        return OutboxPublication(claimed.id, claimed.job_id, True)

    async def publish_available(self, limit: int = 100) -> list[OutboxPublication]:
        """Publish up to ``limit`` recoverable records."""

        if limit < 1:
            raise ValueError("limit must be positive")
        publications: list[OutboxPublication] = []
        for _ in range(limit):
            try:
                publication = await self.publish_once()
            except DispatchFailure:
                break
            if publication is None:
                break
            publications.append(publication)
        return publications

    async def _claim_one(self) -> OutboxDispatch | None:
        now = utc_now()
        lease_until = now + timedelta(seconds=self._lease_seconds)
        async with self._session_factory() as session:
            query = (
                select(OutboxDispatch)
                .where(
                    OutboxDispatch.published_at.is_(None),
                    or_(
                        OutboxDispatch.lease_until.is_(None),
                        OutboxDispatch.lease_until < now,
                    ),
                )
                .order_by(OutboxDispatch.created_at.asc(), OutboxDispatch.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            record = await session.scalar(query)
            if record is None:
                return None
            record.lease_owner = self._publisher_id
            record.lease_until = lease_until
            record.attempt_count += 1
            await session.commit()
            return record

    async def _record_failure(self, outbox_id: UUID, error: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(OutboxDispatch)
                .where(
                    OutboxDispatch.id == outbox_id,
                    OutboxDispatch.lease_owner == self._publisher_id,
                )
                .values(
                    lease_owner=None,
                    lease_until=None,
                    last_error=error[:4000],
                )
            )
            await session.commit()

    async def _mark_published(self, outbox_id: UUID) -> None:
        async with self._session_factory() as session:
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(OutboxDispatch)
                    .where(
                        OutboxDispatch.id == outbox_id,
                        OutboxDispatch.published_at.is_(None),
                        OutboxDispatch.lease_owner == self._publisher_id,
                    )
                    .values(
                        published_at=datetime.now(UTC),
                        lease_owner=None,
                        lease_until=None,
                        last_error=None,
                    )
                ),
            )
            if result.rowcount != 1:
                await session.rollback()
                raise DispatchFailure("Outbox publication could not be finalized.")
            await session.commit()
