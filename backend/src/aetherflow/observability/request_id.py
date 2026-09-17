"""Request ID middleware."""

import re
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aetherflow.observability.context import set_request_id

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
REQUEST_ID_HEADER = "X-Request-ID"


def _validated_request_id(value: str | None) -> str:
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return f"req_{uuid4().hex}"


class RequestIdMiddleware:
    """Propagate a validated request ID and return it in every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied = headers.get(REQUEST_ID_HEADER.lower().encode())
        request_id = _validated_request_id(supplied.decode("latin-1") if supplied else None)
        set_request_id(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message = {**message, "headers": response_headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)
