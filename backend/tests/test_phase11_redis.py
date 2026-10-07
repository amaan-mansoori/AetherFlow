import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from aetherflow.config.settings import Settings
from aetherflow.infrastructure.redis import (
    RateLimitDecision,
    RedisClient,
    RedisRateLimitStore,
)
from aetherflow.observability.rate_limit import RateLimitMiddleware


class FakeRedis:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls: list[tuple[str, int, int]] = []
        self.counts: dict[str, int] = {}
        self.failure = failure
        self._lock = asyncio.Lock()

    async def eval(self, _script: str, _key_count: int, key: str, window: str) -> list[int]:
        if self.failure is not None:
            raise self.failure
        async with self._lock:
            self.calls.append((key, int(window), 1))
            self.counts[key] = self.counts.get(key, 0) + 1
            return [self.counts[key], int(window)]


def settings(**overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        **overrides,
    )


def test_redis_configuration_rejects_non_redis_urls() -> None:
    with pytest.raises(ValueError, match="redis_url"):
        settings(redis_url="https://not-redis.example")


@pytest.mark.asyncio
async def test_redis_client_can_close_without_network_startup() -> None:
    client = RedisClient(settings(redis_enabled=True))
    await client.close()


@pytest.mark.asyncio
async def test_redis_rate_limit_store_uses_atomic_script_and_bounded_decision() -> None:
    client = FakeRedis()
    store = RedisRateLimitStore(client)  # type: ignore[arg-type]

    first = await store.check("aetherflow:ratelimit:v1:api:opaque", 2, 60)
    second = await store.check("aetherflow:ratelimit:v1:api:opaque", 2, 60)

    assert first == RateLimitDecision(count=1, remaining=1, retry_after_seconds=60)
    assert second == RateLimitDecision(count=2, remaining=0, retry_after_seconds=60)
    assert client.calls == [("aetherflow:ratelimit:v1:api:opaque", 60, 1)] * 2


@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks_above_limit_with_retry_after() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings(rate_limit_api_requests=1))
    app.state.rate_limit_store = RedisRateLimitStore(FakeRedis())  # type: ignore[arg-type]

    @app.get("/api/v1/jobs")
    async def jobs() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/api/v1/jobs", headers={"X-API-Key": "afk_publicid_secret"})
        second = await client.get("/api/v1/jobs", headers={"X-API-Key": "afk_publicid_secret"})

    assert first.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "1"
    assert first.headers["x-ratelimit-remaining"] == "0"
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"
    assert second.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_rate_limit_middleware_separates_classes_and_uses_public_id_only() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings(rate_limit_auth_requests=1))
    fake = FakeRedis()
    app.state.rate_limit_store = RedisRateLimitStore(fake)  # type: ignore[arg-type]

    @app.post("/api/v1/auth/login")
    async def login() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/jobs")
    async def jobs() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/login",
            headers={"X-API-Key": "afk_publicid_secret-value-never-in-key"},
        )
        await client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "afk_publicid_secret-value-never-in-key"},
        )

    keys = [call[0] for call in fake.calls]
    assert len(keys) == 2
    assert "auth" in keys[0]
    assert "api" in keys[1]
    assert "secret-value-never-in-key" not in " ".join(keys)
    assert all(len(key) < 100 for key in keys)


@pytest.mark.asyncio
async def test_rate_limit_middleware_fails_open_when_redis_is_unavailable() -> None:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, settings=settings())
    app.state.rate_limit_store = RedisRateLimitStore(
        FakeRedis(failure=TimeoutError("bounded timeout"))
    )  # type: ignore[arg-type]

    @app.get("/api/v1/jobs")
    async def jobs() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/jobs")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
