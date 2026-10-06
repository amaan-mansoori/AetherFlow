"""Authentication and current-user endpoints."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from aetherflow.api.dependencies import get_request_db_session
from aetherflow.api.errors import ApiError
from aetherflow.auth.policies import require_authenticated_user
from aetherflow.auth.schemas import (
    DemoAccessStatus,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from aetherflow.auth.service import (
    authenticate_user,
    create_refresh_session,
    demo_access_available,
    register_user,
    revoke_refresh_session,
    rotate_refresh_session,
    to_user_response,
    user_roles,
    write_audit,
)
from aetherflow.auth.tokens import create_access_token
from aetherflow.config.settings import Settings
from aetherflow.infrastructure.database.models import AuditEventType, User
from aetherflow.observability.context import get_request_id

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
db_session = Depends(get_request_db_session)
authenticated_user = Depends(require_authenticated_user)


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        domain=settings.refresh_cookie_domain,
        path="/api/v1/auth",
        max_age=settings.refresh_token_days * 86400,
    )


def _validate_browser_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.cors_origins:
        raise ApiError("FORBIDDEN", "Request origin is not allowed.", 403)


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    user = await register_user(session, payload.email, payload.password, get_request_id())
    return to_user_response(user)


@router.get("/demo", response_model=DemoAccessStatus)
async def demo_status(
    request: Request,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    return {
        "available": await demo_access_available(session, settings.demo_enabled),
        "access_mode": "read-only",
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    _validate_browser_origin(request, settings)
    user = await authenticate_user(session, payload.email, payload.password, get_request_id())
    refresh_token, family_id = await create_refresh_session(
        session, user, settings, get_request_id()
    )
    access_token = create_access_token(settings, user.id, user_roles(user), family_id)
    _set_refresh_cookie(response, settings, refresh_token)
    return {
        "access_token": access_token,
        "expires_in": settings.access_token_minutes * 60,
        "user": to_user_response(user),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    _validate_browser_origin(request, settings)
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        await write_audit(
            session,
            AuditEventType.TOKEN_REFRESH,
            actor_user_id=None,
            request_id=get_request_id(),
            success=False,
            context={"reason": "missing_refresh_cookie"},
        )
        await session.commit()
        raise ApiError("AUTHENTICATION_REQUIRED", "Refresh authentication is required.", 401)
    user, access_token, new_refresh = await rotate_refresh_session(
        session, token, settings, get_request_id()
    )
    _set_refresh_cookie(response, settings, new_refresh)
    return {
        "access_token": access_token,
        "expires_in": settings.access_token_minutes * 60,
        "user": to_user_response(user),
    }


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = db_session,
) -> None:
    settings: Settings = request.app.state.settings
    _validate_browser_origin(request, settings)
    await revoke_refresh_session(
        session, request.cookies.get(settings.refresh_cookie_name), get_request_id()
    )
    response.delete_cookie(
        settings.refresh_cookie_name,
        domain=settings.refresh_cookie_domain,
        path="/api/v1/auth",
    )


@router.get("/me", response_model=UserResponse)
async def current_user(
    user: User = authenticated_user,
) -> dict[str, object]:
    return to_user_response(user)
