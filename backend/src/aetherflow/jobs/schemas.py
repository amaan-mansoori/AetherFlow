"""Job schemas for validation and API responses."""

from datetime import datetime
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

    @field_validator("type", "model")
    @classmethod
    def string_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()


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


class JobDetailResponse(JobResponse):
    input: dict[str, Any]
    configuration: dict[str, Any]
    retry_policy: dict[str, Any]
    metadata: dict[str, Any]
    result: JobResultResponse | None = None
    latest_attempt: JobAttemptResponse | None = None
