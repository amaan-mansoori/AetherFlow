"""Idempotency fingerprinting and validation operations."""

import hashlib
import json
from typing import Any

from aetherflow.api.errors import ApiError


def compute_payload_fingerprint(payload: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hex digest for a request payload dictionary."""
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def validate_idempotency_key(key: str | None) -> str:
    """Ensure idempotency key is present, non-blank, and within length constraints."""
    if not key or not key.strip():
        raise ApiError("VALIDATION_ERROR", "Idempotency-Key header is required.", 400)
    trimmed = key.strip()
    if len(trimmed) > 128:
        raise ApiError(
            "VALIDATION_ERROR", "Idempotency-Key header cannot exceed 128 characters.", 400
        )
    return trimmed
