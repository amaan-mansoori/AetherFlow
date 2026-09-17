"""Identity, token, API-key, and authorization tests."""

import jwt
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select

from aetherflow.auth.passwords import hash_password
from aetherflow.auth.policies import require_admin
from aetherflow.auth.tokens import generate_api_key
from aetherflow.infrastructure.database.base import Base
from aetherflow.infrastructure.database.models import AuditLog, Role, User


async def register(client: AsyncClient, email: str = "dev@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_registration_normalizes_email_and_never_accepts_role(client: AsyncClient) -> None:
    body = await register(client, " DEV@EXAMPLE.COM ")
    assert body["email"] == "dev@example.com"
    assert body["roles"] == ["USER"]
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_registration_validation_and_duplicate_email(client: AsyncClient) -> None:
    invalid = await client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "short"}
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    await register(client)
    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"email": "DEV@example.com", "password": "correct horse battery staple"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_security_sensitive_extra_fields_are_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin-attempt@example.com",
            "password": "correct horse battery staple",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_malformed_stored_password_hash_is_an_authentication_failure(
    client: AsyncClient, app: FastAPI
) -> None:
    await register(client)
    async with app.state.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "dev@example.com"))
        assert user is not None
        user.password_hash = "not-an-argon2-hash"
        await session.commit()
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct horse battery staple"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_blank_api_key_name_is_rejected(client: AsyncClient) -> None:
    await register(client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct horse battery staple"},
    )
    response = await client.post(
        "/api/v1/api-keys",
        json={"name": "   "},
        headers={"Authorization": "Bearer " + login.json()["access_token"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_login_me_refresh_rotation_and_logout(client: AsyncClient) -> None:
    await register(client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    access = login.json()["access_token"]
    assert jwt.decode(access, options={"verify_signature": False})["typ"] == "access"
    me = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + access})
    assert me.status_code == 200
    old_cookie = client.cookies.get("aetherflow_refresh")
    assert old_cookie is not None
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200
    reused = await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"aetherflow_refresh={old_cookie}"}
    )
    assert reused.status_code == 401
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


@pytest.mark.asyncio
async def test_login_is_generic_for_unknown_user_and_wrong_password(client: AsyncClient) -> None:
    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "correct horse battery staple"},
    )
    await register(client)
    wrong = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "wrong password here"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]


@pytest.mark.asyncio
async def test_expired_and_invalid_access_tokens_are_rejected(client: AsyncClient) -> None:
    expired = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "iat": 1, "exp": 2, "typ": "access"},
        "wrong-secret-that-is-not-the-configured-key",
        algorithm="HS256",
    )
    expired_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + expired}
    )
    malformed_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert expired_response.status_code == malformed_response.status_code == 401


@pytest.mark.asyncio
async def test_api_key_secret_is_one_time_and_revocation_works(client: AsyncClient) -> None:
    await register(client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct horse battery staple"},
    )
    access = login.json()["access_token"]
    created = await client.post(
        "/api/v1/api-keys",
        json={"name": "local-script"},
        headers={"Authorization": "Bearer " + access},
    )
    assert created.status_code == 201
    key = created.json()
    assert key["secret"].startswith("afk_")
    assert "secret_hash" not in key
    listed = await client.get("/api/v1/api-keys", headers={"X-API-Key": key["secret"]})
    assert listed.status_code == 200
    assert "secret" not in listed.text
    revoked = await client.delete(
        "/api/v1/api-keys/" + key["id"],
        headers={"Authorization": "Bearer " + access},
    )
    assert revoked.status_code == 204
    rejected = await client.get("/api/v1/api-keys", headers={"X-API-Key": key["secret"]})
    assert rejected.status_code == 401


@pytest.mark.asyncio
async def test_security_actions_create_audit_events(client: AsyncClient, app: FastAPI) -> None:
    await register(client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct horse battery staple"},
    )
    access = login.json()["access_token"]
    await client.post(
        "/api/v1/api-keys",
        json={"name": "audit-check"},
        headers={"Authorization": "Bearer " + access},
    )
    async with app.state.session_factory() as session:
        events = list((await session.scalars(select(AuditLog))).all())
    event_types = {event.event_type for event in events}
    assert {"REGISTRATION", "LOGIN_SUCCESS", "API_KEY_CREATED"} <= event_types


@pytest.mark.asyncio
async def test_ambiguous_authentication_is_rejected(client: AsyncClient) -> None:
    await register(client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dev@example.com", "password": "correct horse battery staple"},
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer " + login.json()["access_token"],
            "X-API-Key": "afk_bad_bad",
        },
    )
    assert response.status_code == 401


def test_api_key_uses_high_entropy_secret() -> None:
    first, _, first_hash = generate_api_key()
    second, _, second_hash = generate_api_key()
    assert first != second
    assert first_hash != second_hash
    assert len(first.split("_", 2)[2]) >= 40


@pytest.mark.asyncio
async def test_admin_dependency_denies_user(database_engine) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(database_engine, expire_on_commit=False)
    async with factory() as session:
        role = Role(name="USER")
        user = User(
            email="user@example.com",
            password_hash=hash_password("correct horse battery staple"),
            roles=[role],
        )
        session.add(user)
        await session.commit()
        with pytest.raises(Exception) as error:
            await require_admin(None, session, user)  # type: ignore[arg-type]
        assert getattr(error.value, "code", None) == "FORBIDDEN"
