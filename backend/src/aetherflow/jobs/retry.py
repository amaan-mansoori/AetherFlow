"""Deterministic bounded retry policy for internal dispatch recovery."""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import cast

from aetherflow.jobs.execution import ExecutionFailure, ExecutionFailureKind


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


class ExecutionRetryDecision(StrEnum):
    RETRY = "RETRY"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True)
class ExecutionRetryPolicy:
    """Deterministic policy for provider execution failures."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.initial_backoff_seconds <= 0 or self.max_backoff_seconds <= 0:
            raise ValueError("backoff values must be positive")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least one")

    @classmethod
    def from_job_configuration(cls, configuration: dict[str, object]) -> "ExecutionRetryPolicy":
        values = {
            "max_attempts": configuration.get("max_attempts", 3),
            "initial_backoff_seconds": configuration.get("initial_backoff_seconds", 1.0),
            "max_backoff_seconds": configuration.get("max_backoff_seconds", 60.0),
            "backoff_multiplier": configuration.get("backoff_multiplier", 2.0),
        }
        try:
            return cls(
                max_attempts=int(cast(int | str | float, values["max_attempts"])),
                initial_backoff_seconds=float(
                    cast(int | str | float, values["initial_backoff_seconds"])
                ),
                max_backoff_seconds=float(cast(int | str | float, values["max_backoff_seconds"])),
                backoff_multiplier=float(cast(int | str | float, values["backoff_multiplier"])),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid execution retry policy") from exc

    def decision_for(
        self, failure: ExecutionFailure, attempt_number: int
    ) -> tuple[ExecutionRetryDecision, timedelta | None]:
        if attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        retryable = {
            ExecutionFailureKind.RATE_LIMIT,
            ExecutionFailureKind.TIMEOUT,
            ExecutionFailureKind.TRANSIENT_PROVIDER,
        }
        if failure.kind not in retryable or attempt_number >= self.max_attempts:
            return ExecutionRetryDecision.TERMINAL, None
        delay = min(
            self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt_number - 1)),
            self.max_backoff_seconds,
        )
        return ExecutionRetryDecision.RETRY, timedelta(seconds=delay)
