"""Centralized API error types and handlers."""

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from aetherflow.observability.context import get_request_id

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Expected application error represented by the public error contract."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": get_request_id(),
                "details": details or {},
            }
        },
    )


async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
    details = {
        "fields": [{"location": error["loc"], "message": error["msg"]} for error in exc.errors()]
    }
    return _error_response(400, "VALIDATION_ERROR", "Request validation failed.", details)


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    message = str(exc.detail) if isinstance(exc.detail, str) else "HTTP request failed."
    return _error_response(exc.status_code, code, message)


async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_info=exc)
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")
