"""Dispatch boundary for future message-broker implementations."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class DispatchFailure(RuntimeError):
    """Raised when a dispatcher cannot accept a durable dispatch message."""


@dataclass(frozen=True)
class DispatchMessage:
    """Minimal broker-neutral message for one executable job."""

    job_id: UUID
    job_version: int
    enqueued_at: datetime


class JobDispatcher(Protocol):
    """Publish and receive executable job messages."""

    async def dispatch(self, message: DispatchMessage) -> None:
        """Accept a message or raise ``DispatchFailure``."""

    async def receive(self) -> DispatchMessage:
        """Receive the next message."""


class LocalDispatcher:
    """In-process test dispatcher; it provides no distributed guarantees."""

    def __init__(self) -> None:
        self._messages: asyncio.Queue[DispatchMessage] = asyncio.Queue()

    async def dispatch(self, message: DispatchMessage) -> None:
        await self._messages.put(message)

    async def receive(self) -> DispatchMessage:
        return await self._messages.get()
