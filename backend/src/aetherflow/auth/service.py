"""Identity, session, API-key, and audit application services."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aetherflow.api.errors import ApiError
from aetherflow.auth.passwords import hash_password, verify_password
from aetherflow.auth.tokens import (
    create_access_token,
    generate_api_key,
    generate_refresh_token,
    hash_refresh_token,
)
from aetherflow.config.settings import Settings
from aetherflow.infrastructure.database.models import (
    ApiKey,
    AuditEventType,
    AuditLog,
    RefreshSession,
    Role,
    User,
    UserStatus,
    utc_now,
)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def normalize_email(email: str) -> str:
    return email.strip().lower()


def user_roles(user: User) -> list[str]:
    return sorted(role.name for role in user.roles)


def to_user_response(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "roles": user_roles(user),
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


async def write_audit(
    session: AsyncSession,
    event_type: AuditEventType,
    *,
    actor_user_id: UUID | None,
    request_id: str | None,
    success: bool,
    source: str | None = None,
    context: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            event_type=event_type,
            actor_user_id=actor_user_id,
            request_id=request_id,
            success=success,
            source=source,
            context=context or {},
        )
    )


async def get_user_role(session: AsyncSession, name: str) -> Role:
    role = await session.scalar(select(Role).where(Role.name == name))
    if role is None:
        raise RuntimeError(f"required role is missing: {name}")
    return role


async def register_user(
    session: AsyncSession, email: str, password: str, request_id: str | None
) -> User:
    user = User(email=normalize_email(email), password_hash=hash_password(password))
    user.roles.append(await get_user_role(session, "USER"))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        await write_audit(
            session,
            AuditEventType.REGISTRATION,
            actor_user_id=None,
            request_id=request_id,
            success=False,
            context={"reason": "duplicate_email"},
        )
        raise ApiError("CONFLICT", "An account with this email already exists.", 409) from exc
    await write_audit(
        session,
        AuditEventType.REGISTRATION,
        actor_user_id=user.id,
        request_id=request_id,
        success=True,
    )
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user


async def authenticate_user(
    session: AsyncSession, settings: Settings, email: str, password: str, request_id: str | None
) -> tuple[User, str]:
    normalized = normalize_email(email)
    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.email == normalized)
    )
    valid = (
        user is not None
        and user.status == UserStatus.ACTIVE
        and verify_password(password, user.password_hash)
    )
    if not valid:
        await write_audit(
            session,
            AuditEventType.LOGIN_FAILURE,
            actor_user_id=user.id if user else None,
            request_id=request_id,
            success=False,
            context={"reason": "invalid_credentials"},
        )
        await session.commit()
        raise ApiError("AUTHENTICATION_REQUIRED", "Invalid email or password.", 401)
    assert user is not None
    user.last_login_at = utc_now()
    token = create_access_token(settings, user.id, user_roles(user))
    await write_audit(
        session,
        AuditEventType.LOGIN_SUCCESS,
        actor_user_id=user.id,
        request_id=request_id,
        success=True,
    )
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user, token


async def create_refresh_session(
    session: AsyncSession, user: User, settings: Settings, request_id: str | None
) -> str:
    raw, token_hash, family_id = generate_refresh_token()
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
        )
    )
    await write_audit(
        session,
        AuditEventType.TOKEN_REFRESH,
        actor_user_id=user.id,
        request_id=request_id,
        success=True,
        context={"operation": "session_created"},
    )
    await session.commit()
    return raw


async def rotate_refresh_session(
    session: AsyncSession, raw_token: str, settings: Settings, request_id: str | None
) -> tuple[User, str, str]:
    token_hash = hash_refresh_token(raw_token)
    current = await session.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash).with_for_update()
    )
    now = utc_now()
    if current is None or current.revoked_at is not None or current.rotated_at is not None:
        if current is not None:
            await session.execute(
                update(RefreshSession)
                .where(RefreshSession.family_id == current.family_id)
                .values(revoked_at=now)
            )
        await write_audit(
            session,
            AuditEventType.TOKEN_REFRESH,
            actor_user_id=current.user_id if current else None,
            request_id=request_id,
            success=False,
            context={"reason": "invalid_or_reused_refresh_token"},
        )
        await session.commit()
        raise ApiError("AUTHENTICATION_REQUIRED", "Invalid refresh credential.", 401)
    if _as_utc(current.expires_at) <= now:
        current.revoked_at = now
        await write_audit(
            session,
            AuditEventType.TOKEN_REFRESH,
            actor_user_id=current.user_id,
            request_id=request_id,
            success=False,
            context={"reason": "expired_refresh_token"},
        )
        await session.commit()
        raise ApiError("AUTHENTICATION_REQUIRED", "Invalid refresh credential.", 401)
    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == current.user_id)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        await write_audit(
            session,
            AuditEventType.TOKEN_REFRESH,
            actor_user_id=current.user_id,
            request_id=request_id,
            success=False,
            context={"reason": "inactive_or_missing_user"},
        )
        await session.commit()
        raise ApiError("AUTHENTICATION_REQUIRED", "Invalid refresh credential.", 401)
    current.rotated_at = now
    raw, new_hash, _ = generate_refresh_token()
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=new_hash,
            family_id=current.family_id,
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
    )
    access = create_access_token(settings, user.id, user_roles(user))
    await write_audit(
        session,
        AuditEventType.TOKEN_REFRESH,
        actor_user_id=user.id,
        request_id=request_id,
        success=True,
    )
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user, access, raw


async def revoke_refresh_session(
    session: AsyncSession, raw_token: str | None, request_id: str | None
) -> None:
    if raw_token:
        session_token = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(raw_token))
        )
        if session_token and session_token.revoked_at is None:
            session_token.revoked_at = utc_now()
            await write_audit(
                session,
                AuditEventType.LOGOUT,
                actor_user_id=session_token.user_id,
                request_id=request_id,
                success=True,
            )
    await session.commit()


async def create_api_key(
    session: AsyncSession, user: User, name: str, request_id: str | None
) -> tuple[ApiKey, str]:
    raw, public_id, secret_hash = generate_api_key()
    key = ApiKey(user_id=user.id, name=name, public_id=public_id, secret_hash=secret_hash)
    session.add(key)
    await write_audit(
        session,
        AuditEventType.API_KEY_CREATED,
        actor_user_id=user.id,
        request_id=request_id,
        success=True,
        context={"public_id": public_id},
    )
    await session.commit()
    await session.refresh(key)
    return key, raw


async def revoke_api_key(
    session: AsyncSession, user: User, key_id: UUID, request_id: str | None
) -> None:
    key = await session.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if key is None:
        raise ApiError("NOT_FOUND", "API key not found.", 404)
    if key.revoked_at is None:
        key.revoked_at = utc_now()
        await write_audit(
            session,
            AuditEventType.API_KEY_REVOKED,
            actor_user_id=user.id,
            request_id=request_id,
            success=True,
            context={"public_id": key.public_id},
        )
    await session.commit()
