"""Reusable authentication and authorization dependencies."""

import hashlib
import hmac
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aetherflow.api.dependencies import get_request_db_session
from aetherflow.api.errors import ApiError
from aetherflow.auth.service import write_audit
from aetherflow.auth.tokens import decode_access_token
from aetherflow.config.settings import Settings
from aetherflow.infrastructure.database.models import (
    ApiKey,
    AuditEventType,
    User,
    UserStatus,
    utc_now,
)
from aetherflow.observability.context import get_request_id

Session = Annotated[AsyncSession, Depends(get_request_db_session)]


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _unauthenticated() -> ApiError:
    return ApiError("AUTHENTICATION_REQUIRED", "Authentication is required.", 401)


async def _user_from_access_token(session: AsyncSession, settings: Settings, token: str) -> User:
    try:
        payload = decode_access_token(settings, token)
        if payload.get("typ") != "access":
            raise InvalidTokenError("wrong token type")
        user_id = UUID(str(payload["sub"]))
    except (InvalidTokenError, ValueError, KeyError, TypeError) as exc:
        raise _unauthenticated() from exc
    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise _unauthenticated()
    return user


async def _user_from_api_key(session: AsyncSession, raw_key: str) -> User:
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != "afk":
        raise _unauthenticated()
    public_id, secret = parts[1], parts[2]
    key = await session.scalar(select(ApiKey).where(ApiKey.public_id == public_id))
    if key is None or key.revoked_at is not None:
        raise _unauthenticated()
    if not hmac.compare_digest(key.secret_hash, hashlib.sha256(secret.encode()).hexdigest()):
        raise _unauthenticated()
    key.last_used_at = utc_now()
    await session.commit()
    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == key.user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise _unauthenticated()
    return user


async def require_authenticated_user(request: Request, session: Session) -> User:
    authorization = request.headers.get("Authorization")
    api_key = request.headers.get("X-API-Key")
    if authorization and api_key:
        raise ApiError("AUTHENTICATION_REQUIRED", "Use one authentication mechanism.", 401)
    if api_key:
        user = await _user_from_api_key(session, api_key)
        return user
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthenticated()
    return await _user_from_access_token(session, _settings(request), authorization[7:])


async def require_admin(
    _request: Request,
    session: Session,
    user: Annotated[User, Depends(require_authenticated_user)],
) -> User:
    if not any(role.name == "ADMIN" for role in user.roles):
        await write_audit(
            session,
            AuditEventType.AUTHORIZATION_DENIED,
            actor_user_id=user.id,
            request_id=get_request_id(),
            success=False,
            context={"required_role": "ADMIN"},
        )
        await session.commit()
        raise ApiError("FORBIDDEN", "You do not have permission to perform this action.", 403)
    return user
