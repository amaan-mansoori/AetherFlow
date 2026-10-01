"""Single-message worker orchestration for Phase 4A."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from aetherflow.api.errors import ApiError
from aetherflow.infrastructure.database.models import Job, JobAttempt, JobState, utc_now
from aetherflow.jobs.dispatch import DispatchMessage, JobDispatcher
from aetherflow.jobs.execution import (
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionRequest,
    JobExecutor,
)
from aetherflow.jobs.service import (
    record_job_attempt,
    record_job_result,
    transition_job_state,
)
from aetherflow.jobs.state_machine import is_terminal_state


class WorkerResultStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INELIGIBLE = "INELIGIBLE"


@dataclass(frozen=True)
class WorkerResult:
    """Observable result of processing one dispatch message."""

    job_id: UUID
    status: WorkerResultStatus
    attempt_number: int | None = None
    error_kind: ExecutionFailureKind | None = None


class Worker:
    """Process one message while keeping execution outside DB transactions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dispatcher: JobDispatcher,
        executor: JobExecutor,
        worker_id: str = "local-worker",
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._executor = executor
        self._worker_id = worker_id

    async def run_once(self) -> WorkerResult:
        message = await self._dispatcher.receive()
        async with self._session_factory() as session:
            result = await self.process_message(session, message)
        await self._dispatcher.acknowledge(message)
        return result

    async def process_message(
        self, session: AsyncSession, message: DispatchMessage
    ) -> WorkerResult:
        job = await self._load_job(session, message.job_id)
        if job is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        if is_terminal_state(job.state):
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)

        if job.state == JobState.CANCEL_REQUESTED:
            await transition_job_state(
                session,
                job.id,
                JobState.CANCELLED,
                actor=self._worker_id,
                payload={"reason": "cancelled_before_execution"},
                expected_version=job.version,
            )
            return WorkerResult(message.job_id, WorkerResultStatus.CANCELLED)
        if message.job_version != job.version:
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)

        if job.state == JobState.ACCEPTED:
            job = await transition_job_state(
                session,
                job.id,
                JobState.QUEUED,
                actor=self._worker_id,
                payload={"reason": "worker_accepted_dispatch"},
                expected_version=job.version,
            )
        if job.state == JobState.RETRY_SCHEDULED:
            job = await transition_job_state(
                session,
                job.id,
                JobState.QUEUED,
                actor=self._worker_id,
                payload={"reason": "retry_dispatch"},
                expected_version=job.version,
            )
        if job.state != JobState.QUEUED:
            return WorkerResult(message.job_id, WorkerResultStatus.INELIGIBLE)

        job = await transition_job_state(
            session,
            job.id,
            JobState.RUNNING,
            actor=self._worker_id,
            payload={"reason": "execution_started"},
            expected_version=job.version,
        )
        attempt_number = len(job.attempts) + 1
        attempt = await record_job_attempt(
            session,
            job.id,
            attempt_number,
            "RUNNING",
            worker_id=self._worker_id,
            model=job.model,
        )
        request = ExecutionRequest(
            job_id=job.id,
            type=job.type,
            model=job.model,
            input=job.input,
            configuration=job.configuration,
            timeout_seconds=job.timeout_seconds,
            metadata=job.metadata_,
        )

        try:
            outcome = await self._executor.execute(request)
        except ExecutionFailure as failure:
            await self._finish_attempt(session, attempt.id, "FAILED", failure)
            if failure.kind == ExecutionFailureKind.CANCELLATION:
                await self._cancel_after_execution_failure(session, job)
                return WorkerResult(
                    message.job_id,
                    WorkerResultStatus.CANCELLED,
                    attempt_number,
                    failure.kind,
                )
            await self._fail_job(session, job, failure)
            return WorkerResult(
                message.job_id,
                WorkerResultStatus.FAILED,
                attempt_number,
                failure.kind,
            )
        except Exception as exc:
            unexpected_failure = ExecutionFailure(ExecutionFailureKind.UNEXPECTED, str(exc))
            await self._finish_attempt(session, attempt.id, "FAILED", unexpected_failure)
            await self._fail_job(session, job, unexpected_failure)
            return WorkerResult(
                message.job_id,
                WorkerResultStatus.FAILED,
                attempt_number,
                unexpected_failure.kind,
            )

        await self._finish_attempt(session, attempt.id, "SUCCEEDED", None)
        await record_job_result(
            session,
            job.id,
            outcome.output,
            schema_version=outcome.schema_version,
            usage=outcome.usage,
        )
        current = await self._load_job(session, job.id)
        if current is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        await transition_job_state(
            session,
            job.id,
            JobState.SUCCEEDED,
            actor=self._worker_id,
            payload={"reason": "execution_succeeded"},
            expected_version=current.version,
        )
        return WorkerResult(message.job_id, WorkerResultStatus.SUCCEEDED, attempt_number)

    async def _load_job(self, session: AsyncSession, job_id: UUID) -> Job | None:
        return await session.scalar(
            select(Job)
            .options(selectinload(Job.result), selectinload(Job.attempts))
            .where(Job.id == job_id)
        )

    async def _finish_attempt(
        self,
        session: AsyncSession,
        attempt_id: UUID,
        status: str,
        failure: ExecutionFailure | None,
    ) -> None:
        attempt = await session.get(JobAttempt, attempt_id)
        if attempt is None:
            raise ApiError("NOT_FOUND", "Job attempt not found.", 404)
        attempt.status = status
        attempt.completed_at = utc_now()
        if failure is not None:
            attempt.error_class = failure.kind.value
            attempt.error_message = failure.message
        await session.commit()

    async def _fail_job(self, session: AsyncSession, job: Job, failure: ExecutionFailure) -> None:
        current = await self._load_job(session, job.id)
        if current is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        target = JobState.FAILED
        await transition_job_state(
            session,
            current.id,
            target,
            actor=self._worker_id,
            payload={"reason": "execution_failed", "failure_kind": failure.kind.value},
            expected_version=current.version,
        )

    async def _cancel_after_execution_failure(self, session: AsyncSession, job: Job) -> None:
        current = await self._load_job(session, job.id)
        if current is None:
            raise ApiError("NOT_FOUND", "Job not found.", 404)
        if current.state == JobState.RUNNING:
            current = await transition_job_state(
                session,
                current.id,
                JobState.CANCEL_REQUESTED,
                actor=self._worker_id,
                payload={"reason": "executor_cancellation"},
                expected_version=current.version,
            )
        if current.state == JobState.CANCEL_REQUESTED:
            await transition_job_state(
                session,
                current.id,
                JobState.CANCELLED,
                actor=self._worker_id,
                payload={"reason": "executor_cancellation_completed"},
                expected_version=current.version,
            )
