"""Structured logging configuration."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from aetherflow.observability.context import get_request_id


class JsonFormatter(logging.Formatter):
    """Render log records as compact JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": "aetherflow-api",
            "environment": getattr(record, "environment", None),
            "event": record.getMessage(),
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps({key: value for key, value in payload.items() if value is not None})


def configure_logging(level: str) -> None:
    """Configure one application handler without duplicating handlers on reload."""

    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
