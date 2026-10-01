"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from aetherflow.config.settings import Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AETHERFLOW_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_wildcard_cors_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+aiosqlite:///:memory:", cors_origins=["*"])


def test_logging_level_is_normalized() -> None:
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", logging_level="debug")
    assert settings.logging_level == "DEBUG"


def test_production_requires_kafka_and_secure_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            jwt_secret_key="x" * 40,
        )

    settings = Settings(
        environment="production",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
        jwt_secret_key="x" * 40,
        secure_cookies=True,
        kafka_enabled=True,
    )
    assert settings.database_pool_size == 5
