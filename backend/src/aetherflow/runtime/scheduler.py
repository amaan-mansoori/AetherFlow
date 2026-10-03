"""Executable entrypoint for the independent durable scheduler process."""

import asyncio
import logging
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncEngine

from aetherflow.config.settings import get_settings
from aetherflow.infrastructure.database.session import create_engine, create_session_factory
from aetherflow.jobs.scheduler import DurableScheduler
from aetherflow.observability.metrics import METRICS

logger = logging.getLogger(__name__)


class SchedulerLifecycle(StrEnum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class SchedulerRuntime:
    """Poll durable schedule metadata until graceful shutdown."""

    def __init__(
        self,
        scheduler: DurableScheduler,
        engine: AsyncEngine,
        *,
        poll_interval_seconds: float = 1.0,
        batch_size: int = 100,
    ) -> None:
        if poll_interval_seconds <= 0 or batch_size < 1:
            raise ValueError("poll interval and batch size must be positive")
        self._scheduler = scheduler
        self._engine = engine
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.lifecycle = SchedulerLifecycle.STOPPED

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("scheduler runtime is already started")
        self._stop_event.clear()
        self.lifecycle = SchedulerLifecycle.STARTING
        self._task = asyncio.create_task(self.run(), name="aetherflow-scheduler")
        await asyncio.sleep(0)

    async def run(self) -> None:
        self.lifecycle = SchedulerLifecycle.RUNNING
        METRICS.inc("aetherflow_scheduler_active_state_total", state="RUNNING")
        try:
            while not self._stop_event.is_set():
                try:
                    await self._scheduler.poll_once(self._batch_size)
                except Exception:
                    METRICS.inc("aetherflow_scheduler_errors_total")
                    logger.error("scheduler_iteration_failed", exc_info=True)
                await self._wait_for_next_poll()
        finally:
            self.lifecycle = SchedulerLifecycle.STOPPING
            METRICS.inc("aetherflow_scheduler_active_state_total", state="STOPPING")
            await self._engine.dispose()
            self.lifecycle = SchedulerLifecycle.STOPPED
            METRICS.inc("aetherflow_scheduler_active_state_total", state="STOPPED")

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        if task is not None:
            await task
            self._task = None

    async def wait(self) -> None:
        if self._task is None:
            raise RuntimeError("scheduler runtime is not started")
        await self._task

    async def _wait_for_next_poll(self) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
        except TimeoutError:
            return


async def run() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    if not settings.scheduler_enabled:
        logger.info("scheduler_disabled")
        await engine.dispose()
        return
    scheduler = DurableScheduler(
        create_session_factory(engine),
        scheduler_id=settings.scheduler_id,
    )
    runtime = SchedulerRuntime(
        scheduler,
        engine,
        poll_interval_seconds=settings.scheduler_poll_interval_seconds,
        batch_size=settings.scheduler_batch_size,
    )
    await runtime.start()
    try:
        await runtime.wait()
    finally:
        await runtime.stop()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
