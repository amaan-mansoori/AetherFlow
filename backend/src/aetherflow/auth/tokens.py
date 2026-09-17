"""JWT access-token and opaque refresh-token operations."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from aetherflow.config.settings import Settings

ACCESS_TOKEN_ALGORITHM = "HS256"


def create_access_token(settings: Settings, user_id: UUID, roles: list[str]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ACCESS_TOKEN_ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[ACCESS_TOKEN_ALGORITHM],
        options={"require": ["sub", "iat", "exp", "typ"]},
    )


def generate_refresh_token() -> tuple[str, str, UUID]:
    token = secrets.token_urlsafe(48)
    return token, hash_refresh_token(token), uuid4()


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    public_id = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]
    secret = secrets.token_urlsafe(32)
    return f"afk_{public_id}_{secret}", public_id, hashlib.sha256(secret.encode()).hexdigest()
