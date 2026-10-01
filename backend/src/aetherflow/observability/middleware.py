"""HTTP metrics middleware."""

import re
from time import perf_counter
from typing import cast

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aetherflow.observability.metrics import METRICS


class MetricsMiddleware:
    """Record bounded HTTP metrics without inspecting request payloads."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        status_code = 500

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(cast(int, message["status"]))
            await send(message)

        await self.app(scope, receive, send_with_status)
        route = getattr(scope.get("route"), "path", None) or "unmatched"
        route = re.sub(r"\{[^}]+\}", ":param", route)
        status_class = f"{status_code // 100}xx"
        labels: dict[str, str] = {
            "method": str(scope["method"]),
            "route": route,
            "status_class": status_class,
        }
        METRICS.inc(
            "aetherflow_http_requests_total",
            method=labels["method"],
            route=labels["route"],
            status_class=labels["status_class"],
        )
        if status_code >= 400:
            METRICS.inc(
                "aetherflow_http_errors_total",
                method=labels["method"],
                route=labels["route"],
                status_class=labels["status_class"],
            )
        METRICS.observe(
            "aetherflow_http_request_duration_seconds",
            perf_counter() - started,
            method=str(scope["method"]),
            route=route,
        )
