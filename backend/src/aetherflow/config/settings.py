"""Typed, environment-driven application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AETHERFLOW_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Environment = "development"
    application_name: str = "AetherFlow API"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str
    jwt_secret_key: str
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    refresh_cookie_name: str = "aetherflow_refresh"
    secure_cookies: bool = False
    refresh_cookie_domain: str | None = None
    demo_enabled: bool = False
    logging_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)
    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "aetherflow.jobs"
    kafka_consumer_group: str = "aetherflow-workers"
    kafka_client_id: str = "aetherflow"
    kafka_auto_offset_reset: Literal["earliest", "latest"] = "earliest"
    kafka_producer_enable_idempotence: bool = True
    worker_id: str = Field(default="aetherflow-worker", min_length=1, max_length=128)
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    outbox_poll_interval_seconds: float = Field(default=1.0, gt=0, le=300)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_lease_seconds: int = Field(default=60, ge=1, le=3600)
    outbox_max_attempts: int = Field(default=5, ge=1, le=100)
    outbox_initial_backoff_seconds: float = Field(default=1.0, gt=0, le=3600)
    outbox_max_backoff_seconds: float = Field(default=300.0, gt=0, le=86400)
    outbox_publisher_id: str | None = Field(default=None, max_length=128)
    scheduler_enabled: bool = False
    scheduler_poll_interval_seconds: float = Field(default=1.0, gt=0, le=300)
    scheduler_batch_size: int = Field(default=100, ge=1, le=1000)
    scheduler_id: str = Field(default="aetherflow-scheduler", min_length=1, max_length=128)
    provider_default: str = Field(default="mock", min_length=1, max_length=64)
    provider_openai_api_key: str | None = Field(
        default=None,
        min_length=1,
        validate_default=True,
    )
    provider_openai_base_url: str = "https://api.openai.com/v1"
    provider_openai_max_connections: int = Field(default=10, ge=1, le=100)
    provider_openai_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = Field(default=10, ge=1, le=100)
    redis_connect_timeout_seconds: float = Field(default=1.0, gt=0, le=30)
    redis_socket_timeout_seconds: float = Field(default=1.0, gt=0, le=30)
    rate_limit_auth_requests: int = Field(default=20, ge=1, le=10000)
    rate_limit_api_requests: int = Field(default=120, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    @field_validator("logging_level")
    @classmethod
    def normalize_logging_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("logging_level must be a standard Python logging level")
        return normalized

    @field_validator("provider_openai_api_key", mode="before")
    @classmethod
    def normalize_empty_openai_api_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("provider_default")
    @classmethod
    def normalize_provider_default(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("provider_default must not be blank")
        return normalized

    @field_validator("provider_openai_base_url")
    @classmethod
    def validate_provider_openai_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("provider_openai_base_url must be an HTTP(S) URL")
        return normalized

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must be a redis:// or rediss:// URL")
        return normalized

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str], info: object) -> list[str]:
        if "*" in value:
            raise ValueError("wildcard CORS origins are not allowed")
        return [origin.rstrip("/") for origin in value if origin.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if len(self.jwt_secret_key) < 32:
            raise ValueError("jwt_secret_key must contain at least 32 characters")
        if self.environment == "production" and not self.secure_cookies:
            raise ValueError("secure_cookies must be enabled in production")
        if self.environment == "production" and not self.kafka_enabled:
            raise ValueError("kafka_enabled must be enabled in production")
        if self.provider_default == "openai" and not self.provider_openai_api_key:
            raise ValueError(
                "provider_openai_api_key is required when openai is the default provider"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable-in-practice settings object."""

    return Settings()  # type: ignore[call-arg]
