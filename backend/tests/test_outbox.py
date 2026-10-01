"""Transactional outbox and publication recovery tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from aetherflow.infrastructure.database.models import IdempotencyRecord, Job, OutboxDispatch
from aetherflow.jobs.dispatch import DispatchFailure, DispatchMessage, LocalDispatcher
from aetherflow.jobs.outbox import OutboxPublisher
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import submit_job


async def create_submission(app, email: str):
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(session, email, "correct horse battery staple", None)
        job, is_new = await submit_job(
            session,
            user,
            JobCreateRequest(model="outbox-test", input={"prompt": "test"}),
            f"outbox-{email}",
        )
        return job, is_new


@pytest.mark.asyncio
async def test_submission_commits_job_and_outbox_intent_together(app) -> None:
    job, is_new = await create_submission(app, "outbox-atomic@example.com")

    assert is_new is True
    async with app.state.session_factory() as session:
        stored_job = await session.scalar(select(Job).where(Job.id == job.id))
        outbox = await session.scalar(select(OutboxDispatch).where(OutboxDispatch.job_id == job.id))
        assert stored_job is not None
        assert outbox is not None
        assert outbox.job_id == job.id
        assert outbox.job_version == job.version
        assert outbox.schema_version == "v1"
        assert outbox.enqueued_at == job.created_at


@pytest.mark.asyncio
async def test_submission_rollback_removes_job_and_outbox(app, monkeypatch) -> None:
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(
            session, "outbox-rollback@example.com", "correct horse battery staple", None
        )

        async def fail_commit() -> None:
            raise RuntimeError("forced transaction failure")

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="forced"):
            await submit_job(
                session,
                user,
                JobCreateRequest(model="outbox-test", input={"prompt": "rollback"}),
                "outbox-rollback",
            )

    async with app.state.session_factory() as session:
        assert await session.scalar(select(Job).where(Job.user_id == user.id)) is None
        assert (
            await session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.idempotency_key == "outbox-rollback"
                )
            )
            is None
        )
        assert await session.scalar(select(func.count()).select_from(OutboxDispatch)) == 0


@pytest.mark.asyncio
async def test_idempotent_replay_does_not_create_second_outbox(app) -> None:
    job, _ = await create_submission(app, "outbox-replay@example.com")

    async with app.state.session_factory() as session:
        from aetherflow.infrastructure.database.models import User

        principal = await session.get(User, job.user_id)
        assert principal is not None
        replay, is_new = await submit_job(
            session,
            principal,
            JobCreateRequest(model="outbox-test", input={"prompt": "test"}),
            "outbox-outbox-replay@example.com",
        )
        assert replay.id == job.id
        assert is_new is False
        count = await session.scalar(
            select(func.count()).select_from(OutboxDispatch).where(OutboxDispatch.job_id == job.id)
        )
        assert count == 1


@pytest.mark.asyncio
async def test_job_mutation_does_not_mutate_dispatch_intent(app) -> None:
    job, _ = await create_submission(app, "outbox-immutable@example.com")
    async with app.state.session_factory() as session:
        original = await session.scalar(
            select(OutboxDispatch).where(OutboxDispatch.job_id == job.id)
        )
        assert original is not None
        original_values = (original.job_version, original.schema_version, original.enqueued_at)

        await session.execute(
            update(Job).where(Job.id == job.id).values(version=2, model="changed-model")
        )
        await session.commit()

        unchanged = await session.scalar(
            select(OutboxDispatch).where(OutboxDispatch.job_id == job.id)
        )
        assert unchanged is not None
        assert (
            unchanged.job_version,
            unchanged.schema_version,
            unchanged.enqueued_at,
        ) == original_values


@pytest.mark.asyncio
async def test_publisher_success_marks_record_published(app) -> None:
    job, _ = await create_submission(app, "outbox-publish@example.com")
    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(app.state.session_factory, dispatcher, publisher_id="publisher-1")

    publication = await publisher.publish_once()

    assert publication is not None
    async with app.state.session_factory() as session:
        outbox = await session.scalar(select(OutboxDispatch).where(OutboxDispatch.job_id == job.id))
        assert outbox is not None
        assert outbox.published_at is not None
        assert outbox.lease_owner is None
    message = await dispatcher.receive()
    assert message == DispatchMessage(job.id, job.version, job.created_at, "v1")


class FailingDispatcher(LocalDispatcher):
    async def dispatch(self, message: DispatchMessage) -> None:
        raise DispatchFailure("Kafka unavailable")


@pytest.mark.asyncio
async def test_publisher_failure_leaves_record_recoverable(app) -> None:
    job, _ = await create_submission(app, "outbox-failure@example.com")
    publisher = OutboxPublisher(
        app.state.session_factory,
        FailingDispatcher(),
        publisher_id="publisher-failure",
    )

    with pytest.raises(DispatchFailure, match="unavailable"):
        await publisher.publish_once()

    async with app.state.session_factory() as session:
        outbox = await session.scalar(select(OutboxDispatch).where(OutboxDispatch.job_id == job.id))
        assert outbox is not None
        assert outbox.published_at is None
        assert outbox.attempt_count == 1
        assert outbox.last_error == "Kafka unavailable"
        assert outbox.lease_owner is None


@pytest.mark.asyncio
async def test_published_records_are_skipped(app) -> None:
    job, _ = await create_submission(app, "outbox-skip@example.com")
    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(
        app.state.session_factory, dispatcher, publisher_id="publisher-skip"
    )

    await publisher.publish_once()
    assert await publisher.publish_once() is None


@pytest.mark.asyncio
async def test_publisher_processes_multiple_records(app) -> None:
    await create_submission(app, "outbox-many-1@example.com")
    await create_submission(app, "outbox-many-2@example.com")
    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(
        app.state.session_factory, dispatcher, publisher_id="publisher-many"
    )

    publications = await publisher.publish_available(limit=2)

    assert len(publications) == 2
    assert await dispatcher.receive()
    assert await dispatcher.receive()


@pytest.mark.asyncio
async def test_publish_success_before_marker_failure_is_recoverable_duplicate(
    app, monkeypatch
) -> None:
    job, _ = await create_submission(app, "outbox-duplicate@example.com")
    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(
        app.state.session_factory, dispatcher, publisher_id="publisher-crash", lease_seconds=1
    )

    async def fail_finalize(outbox_id) -> None:
        raise DispatchFailure("marker persistence failed")

    monkeypatch.setattr(publisher, "_mark_published", fail_finalize)
    with pytest.raises(DispatchFailure, match="marker"):
        await publisher.publish_once()

    async with app.state.session_factory() as session:
        await session.execute(
            update(OutboxDispatch)
            .where(OutboxDispatch.job_id == job.id)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    recovered = OutboxPublisher(
        app.state.session_factory, dispatcher, publisher_id="publisher-recovery"
    )
    await recovered.publish_once()
    assert await dispatcher.receive() == DispatchMessage(job.id, job.version, job.created_at, "v1")
    assert await dispatcher.receive() == DispatchMessage(job.id, job.version, job.created_at, "v1")


@pytest.mark.asyncio
async def test_malformed_outbox_schema_fails_without_dispatch(app) -> None:
    job, _ = await create_submission(app, "outbox-malformed@example.com")
    async with app.state.session_factory() as session:
        await session.execute(
            update(OutboxDispatch)
            .where(OutboxDispatch.job_id == job.id)
            .values(schema_version="unsupported")
        )
        await session.commit()

    dispatcher = LocalDispatcher()
    publisher = OutboxPublisher(
        app.state.session_factory, dispatcher, publisher_id="publisher-malformed"
    )
    with pytest.raises(DispatchFailure, match="Unsupported"):
        await publisher.publish_once()

    async with app.state.session_factory() as session:
        outbox = await session.scalar(select(OutboxDispatch).where(OutboxDispatch.job_id == job.id))
        assert outbox is not None
        assert outbox.published_at is None
        assert outbox.last_error == "Unsupported outbox dispatch type or schema."
    assert dispatcher._messages.empty()
