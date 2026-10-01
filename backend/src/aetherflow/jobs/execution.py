"""Provider-independent execution contracts for durable jobs."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ExecutionFailureKind(StrEnum):
    """Classify failures without coupling the domain to a provider."""

    VALIDATION = "VALIDATION"
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    EXECUTION = "EXECUTION"
    TRANSIENT_PROVIDER = "TRANSIENT_PROVIDER"
    PERMANENT_PROVIDER = "PERMANENT_PROVIDER"
    CANCELLATION = "CANCELLATION"
    UNEXPECTED = "UNEXPECTED"


class ExecutionFailure(Exception):
    """A controlled execution failure returned by an executor."""

    def __init__(
        self,
        kind: ExecutionFailureKind,
        message: str,
        *,
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.provider = provider


@dataclass(frozen=True)
class ExecutionRequest:
    """Immutable job data passed to an executor outside a database transaction."""

    job_id: UUID
    type: str
    model: str
    input: dict[str, object]
    configuration: dict[str, object]
    timeout_seconds: int
    metadata: dict[str, object]


@dataclass(frozen=True)
class ExecutionOutcome:
    """Validated executor output ready for durable result persistence."""

    output: dict[str, object]
    usage: dict[str, object] | None = None
    schema_version: str = "v1"
    provider: str | None = None
    finish_reason: str | None = None


class JobExecutor(Protocol):
    """Execute one immutable request without infrastructure dependencies."""

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        """Return an outcome or raise ``ExecutionFailure``."""


def utc_now() -> datetime:
    """Return an aware UTC timestamp for dispatch metadata."""

    return datetime.now(UTC)
