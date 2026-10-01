"""Fail-open distributed API rate limiting middleware."""

import hashlib
import logging
import re
from time import perf_counter
from typing import cast

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aetherflow.config.settings import Settings
from aetherflow.infrastructure.redis import RateLimitDecision
from aetherflow.observability.context import get_request_id
from aetherflow.observability.metrics import METRICS

logger = logging.getLogger(__name__)
_PUBLIC_ID = re.compile(r"^[A-Za-z0-9]{8,32}$")


class RateLimitMiddleware:
    """Apply bounded Redis-backed limits without making Redis authoritative."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
    ) -> None:
        self.app = app
        self._settings = settings
        self._redis_failure_logged = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        app = scope.get("app")
        state = getattr(app, "state", None)
        store = getattr(state, "rate_limit_store", None)
        if scope["type"] != "http" or store is None:
            await self.app(scope, receive, send)
            return
        rate_class = self._rate_class(cast(str, scope.get("path", "")))
        if rate_class is None:
            await self.app(scope, receive, send)
            return
        limit = (
            self._settings.rate_limit_auth_requests
            if rate_class == "auth"
            else self._settings.rate_limit_api_requests
        )
        key = self._key(rate_class, scope)
        started = perf_counter()
        try:
            decision = await store.check(
                key,
                limit,
                self._settings.rate_limit_window_seconds,
            )
        except Exception:
            METRICS.inc("aetherflow_redis_errors_total", operation="rate_limit")
            METRICS.inc("aetherflow_rate_limit_bypasses_total", rate_class=rate_class)
            if not self._redis_failure_logged:
                logger.warning("redis_rate_limit_bypassed")
                self._redis_failure_logged = True
            await self.app(scope, receive, send)
            return
        self._redis_failure_logged = False
        METRICS.observe(
            "aetherflow_redis_operation_duration_seconds",
            perf_counter() - started,
            operation="rate_limit",
        )
        headers = self._headers(decision, limit)
        if decision.count > limit:
            METRICS.inc("aetherflow_rate_limit_blocked_total", rate_class=rate_class)
            headers["Retry-After"] = str(decision.retry_after_seconds)
            response = JSONResponse(
                {
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Request rate limit exceeded.",
                        "request_id": get_request_id(),
                        "details": {},
                    }
                },
                status_code=429,
                headers=headers,
            )
            await response(scope, receive, send)
            return
        METRICS.inc("aetherflow_rate_limit_requests_total", rate_class=rate_class)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = list(cast(list[tuple[bytes, bytes]], message.get("headers", [])))
                existing.extend((name.encode(), value.encode()) for name, value in headers.items())
                message = {**message, "headers": existing}
            await send(message)

        await self.app(scope, receive, send_with_headers)

    @staticmethod
    def _rate_class(path: str) -> str | None:
        if path.startswith("/api/v1/auth/"):
            return "auth"
        if path.startswith("/api/v1/"):
            return "api"
        return None

    @classmethod
    def _key(cls, rate_class: str, scope: Scope) -> str:
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in cast(list[tuple[bytes, bytes]], scope.get("headers", []))
        }
        api_key = headers.get("x-api-key", "")
        public_id = api_key.split("_", 2)[1] if api_key.startswith("afk_") else ""
        identity = public_id if _PUBLIC_ID.fullmatch(public_id) else cls._client_host(scope)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        return f"aetherflow:ratelimit:v1:{rate_class}:{digest}"

    @staticmethod
    def _client_host(scope: Scope) -> str:
        client = scope.get("client")
        if isinstance(client, tuple) and client and isinstance(client[0], str):
            return client[0][:255]
        return "unknown"

    @staticmethod
    def _headers(decision: RateLimitDecision, limit: int) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(decision.remaining),
        }
