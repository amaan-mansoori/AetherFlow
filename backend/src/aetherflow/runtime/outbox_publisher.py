"""Executable entrypoint for the independent outbox publisher process."""

import asyncio

from aetherflow.config.settings import get_settings
from aetherflow.infrastructure.database.session import create_engine, create_session_factory
from aetherflow.infrastructure.kafka import KafkaDispatcher
from aetherflow.jobs.outbox import OutboxPublisher
from aetherflow.jobs.outbox_runtime import OutboxPublisherRuntime
from aetherflow.jobs.retry import RetryPolicy


async def run() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    dispatcher = await KafkaDispatcher.create(settings)
    publisher = OutboxPublisher(
        session_factory,
        dispatcher,
        publisher_id=settings.outbox_publisher_id,
        lease_seconds=settings.outbox_lease_seconds,
        retry_policy=RetryPolicy(
            max_attempts=settings.outbox_max_attempts,
            initial_backoff_seconds=settings.outbox_initial_backoff_seconds,
            max_backoff_seconds=settings.outbox_max_backoff_seconds,
        ),
    )
    runtime = OutboxPublisherRuntime(
        publisher,
        dispatcher,
        engine,
        poll_interval_seconds=settings.outbox_poll_interval_seconds,
        batch_size=settings.outbox_batch_size,
    )
    await runtime.start()
    try:
        await runtime.wait()
    finally:
        await runtime.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
