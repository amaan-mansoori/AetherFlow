"""Lifecycle-safe Redis coordination primitives."""

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol, cast

from redis.asyncio import Redis  # type: ignore[import-not-found]
from redis.asyncio.connection import ConnectionPool  # type: ignore[import-not-found]

from aetherflow.config.settings import Settings

_RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
  redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of one atomic fixed-window increment."""

    count: int
    remaining: int
    retry_after_seconds: int


class RateLimitStore(Protocol):
    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        """Atomically consume one request from a bounded window."""


class RedisRateLimitStore:
    """Redis-backed fixed-window store with bounded pooled connections."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        raw = await cast(
            Awaitable[object],
            self._client.eval(
                _RATE_LIMIT_SCRIPT,
                1,
                key,
                str(window_seconds),
            ),
        )
        if (
            not isinstance(raw, list)
            or len(raw) != 2
            or not isinstance(raw[0], int)
            or not isinstance(raw[1], int)
        ):
            raise RuntimeError("Redis returned an invalid rate-limit response")
        count, ttl = raw
        return RateLimitDecision(
            count=count,
            remaining=max(0, limit - count),
            retry_after_seconds=max(1, ttl),
        )


class RedisClient:
    """Own one Redis pool for an application process."""

    def __init__(self, settings: Settings) -> None:
        self._pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
            decode_responses=False,
        )
        self._client: Redis = Redis(connection_pool=self._pool)
        self.rate_limits = RedisRateLimitStore(self._client)

    async def ping(self) -> bool:
        """Check Redis availability without exposing connection details."""

        return bool(await self._client.ping())

    async def close(self) -> None:
        """Close the client and its connection pool."""

        await self._client.aclose()


def create_redis_client(settings: Settings) -> RedisClient:
    """Create a process-owned Redis client; callers own its lifecycle."""

    return RedisClient(settings)
