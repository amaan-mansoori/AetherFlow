"""Executable entrypoint for the independent Kafka worker process."""

import asyncio

from aetherflow.config.settings import get_settings
from aetherflow.infrastructure.database.session import create_engine, create_session_factory
from aetherflow.infrastructure.kafka import KafkaDispatcher, KafkaWorkerRunner
from aetherflow.jobs.providers import create_default_provider_executor
from aetherflow.jobs.worker import Worker


async def run() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    dispatcher = await KafkaDispatcher.create_worker_dispatcher(settings)
    executor = create_default_provider_executor(settings)
    worker = Worker(
        create_session_factory(engine),
        dispatcher,
        executor,
        worker_id=settings.worker_id,
    )
    runner = KafkaWorkerRunner(dispatcher, worker)
    try:
        await runner.run_forever()
    finally:
        await executor.close()
        await dispatcher.close()
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
