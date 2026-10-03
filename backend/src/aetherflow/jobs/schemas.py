"""Job schemas for validation and API responses."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aetherflow.infrastructure.database.models import JobState


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_backoff_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    max_backoff_seconds: float = Field(default=60.0, ge=1.0, le=3600.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter: bool = True


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(default="structured_inference", min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=64)
    input: dict[str, Any]
    configuration: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)
    timeout_seconds: int = Field(default=300, ge=5, le=3600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schedule_at: datetime | None = None

    @field_validator("type", "model")
    @classmethod
    def string_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @field_validator("schedule_at")
    @classmethod
    def normalize_schedule_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("schedule_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("configuration")
    @classmethod
    def reject_provider_credentials(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"api_key", "api_secret", "access_token", "credential", "secret", "token"}

        def contains_forbidden_key(candidate: object) -> bool:
            if isinstance(candidate, dict):
                if forbidden.intersection(candidate):
                    return True
                return any(contains_forbidden_key(item) for item in candidate.values())
            if isinstance(candidate, list):
                return any(contains_forbidden_key(item) for item in candidate)
            return False

        if contains_forbidden_key(value):
            raise ValueError("provider credentials must be configured by the runtime")
        return value


class JobResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    schema_version: str
    output: dict[str, Any]
    usage: dict[str, Any] | None = None
    created_at: datetime


class JobAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    attempt_number: int
    status: str
    worker_id: str | None = None
    provider: str | None = None
    model: str | None = None
    error_class: str | None = None
    error_message: str | None = None
    retry_decision: str | None = None
    usage: dict[str, Any] | None = None
    trace_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class JobEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    event_type: str
    prior_state: JobState | None = None
    next_state: JobState
    actor: str
    payload: dict[str, Any]
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: str
    model: str
    state: JobState
    priority: int
    timeout_seconds: int
    version: int
    created_at: datetime
    updated_at: datetime
    schedule_at: datetime | None = None

    @field_validator("schedule_at", mode="before")
    @classmethod
    def ensure_schedule_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            return value.replace(tzinfo=UTC)
        return value


class JobDetailResponse(JobResponse):
    input: dict[str, Any]
    configuration: dict[str, Any]
    retry_policy: dict[str, Any]
    metadata: dict[str, Any]
    result: JobResultResponse | None = None
    latest_attempt: JobAttemptResponse | None = None


class AdminJobResponse(JobResponse):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    model: str


class AdminAttemptResponse(JobAttemptResponse):
    error_message: str | None = Field(default=None, max_length=400)


class AdminEventResponse(JobEventResponse):
    payload: dict[str, Any] = Field(default_factory=dict)


class AdminDispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    job_version: int
    message_type: str
    schema_version: str
    enqueued_at: datetime
    created_at: datetime
    published_at: datetime | None = None
    attempt_count: int
    failure_category: str | None = None
    publication_state: str
    available_at: datetime | None = None
    next_attempt_at: datetime | None = None
    last_error: str | None = Field(default=None, max_length=400)


class AdminJobDetailResponse(AdminJobResponse):
    retry_policy: dict[str, Any]
    metadata: dict[str, Any]
    execution_owner: str | None = None
    execution_dispatch_version: int | None = None
    execution_lease_until: datetime | None = None
    attempts: list[AdminAttemptResponse]
    events: list[AdminEventResponse]
    dispatches: list[AdminDispatchResponse]
