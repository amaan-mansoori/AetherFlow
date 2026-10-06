"""Programmatic API key management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aetherflow.api.dependencies import get_request_db_session
from aetherflow.auth.policies import require_authenticated_user, require_non_demo_user
from aetherflow.auth.schemas import ApiKeyCreatedResponse, ApiKeyCreateRequest, ApiKeyResponse
from aetherflow.auth.service import create_api_key, revoke_api_key
from aetherflow.infrastructure.database.models import ApiKey, User
from aetherflow.observability.context import get_request_id

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])
db_session = Depends(get_request_db_session)
authenticated_user = Depends(require_authenticated_user)
non_demo_user = Depends(require_non_demo_user)


def _metadata(key: ApiKey) -> dict[str, object]:
    return {
        "id": key.id,
        "name": key.name,
        "public_id": key.public_id,
        "created_at": key.created_at,
        "last_used_at": key.last_used_at,
        "revoked_at": key.revoked_at,
    }


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_key(
    payload: ApiKeyCreateRequest,
    user: User = non_demo_user,
    session: AsyncSession = db_session,
) -> dict[str, object]:
    key, secret = await create_api_key(session, user, payload.name, get_request_id())
    return {**_metadata(key), "secret": secret}


@router.get("", response_model=list[ApiKeyResponse])
async def list_keys(
    user: User = authenticated_user,
    session: AsyncSession = db_session,
) -> list[dict[str, object]]:
    keys = await session.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    )
    return [_metadata(key) for key in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: UUID,
    user: User = non_demo_user,
    session: AsyncSession = db_session,
) -> None:
    await revoke_api_key(session, user, key_id, get_request_id())
