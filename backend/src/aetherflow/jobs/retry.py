"""Deterministic bounded retry policy for internal dispatch recovery."""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum


class FailureCategory(StrEnum):
    TRANSIENT_DISPATCH = "TRANSIENT_DISPATCH"
    PERMANENT_DISPATCH = "PERMANENT_DISPATCH"
    DATABASE = "DATABASE"
    SHUTDOWN = "SHUTDOWN"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.initial_backoff_seconds <= 0 or self.max_backoff_seconds <= 0:
            raise ValueError("backoff values must be positive")

    def delay_for_attempt(self, attempt: int) -> timedelta:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        delay = min(
            self.initial_backoff_seconds * (2 ** (attempt - 1)),
            self.max_backoff_seconds,
        )
        return timedelta(seconds=delay)
