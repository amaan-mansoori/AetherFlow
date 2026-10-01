"""Independent continuously-running outbox publisher runtime."""

import asyncio
import logging
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncEngine

from aetherflow.jobs.dispatch import DispatchFailure, JobDispatcher
from aetherflow.jobs.outbox import OutboxPublisher

logger = logging.getLogger(__name__)


class PublisherLifecycle(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class OutboxPublisherRuntime:
    """Poll bounded outbox batches until stopped, outside the API lifecycle."""

    def __init__(
        self,
        publisher: OutboxPublisher,
        dispatcher: JobDispatcher,
        engine: AsyncEngine,
        *,
        poll_interval_seconds: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        if poll_interval_seconds <= 0 or batch_size < 1:
            raise ValueError("poll interval and batch size must be positive")
        self._publisher = publisher
        self._dispatcher = dispatcher
        self._engine = engine
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.lifecycle = PublisherLifecycle.STOPPED

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("publisher runtime is already started")
        self._stop_event.clear()
        self.lifecycle = PublisherLifecycle.STARTING
        self._task = asyncio.create_task(self.run(), name="aetherflow-outbox-publisher")
        await asyncio.sleep(0)

    async def run(self) -> None:
        self.lifecycle = PublisherLifecycle.RUNNING
        try:
            while not self._stop_event.is_set():
                try:
                    await self._publisher.publish_available(self._batch_size)
                except DispatchFailure:
                    logger.warning("outbox_batch_failed", exc_info=True)
                except Exception:
                    logger.error("outbox_runtime_iteration_failed", exc_info=True)
                await self._wait_for_next_poll()
        finally:
            self.lifecycle = PublisherLifecycle.STOPPING
            await self._dispatcher.close()
            await self._engine.dispose()
            self.lifecycle = PublisherLifecycle.STOPPED

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        if task is not None:
            await task
            self._task = None

    async def wait(self) -> None:
        """Wait for the runtime task, primarily for a process entrypoint."""

        if self._task is None:
            raise RuntimeError("publisher runtime is not started")
        await self._task

    async def _wait_for_next_poll(self) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
        except TimeoutError:
            return
