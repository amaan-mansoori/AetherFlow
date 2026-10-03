"""Phase 13 administrative control-plane regression coverage."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from aetherflow.auth.service import get_user_role
from aetherflow.infrastructure.database.models import AuditEventType, AuditLog, User


async def _register(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _make_admin(app, client: AsyncClient) -> str:
    email = "admin@example.com"
    token = await _register(client, email)
    async with app.state.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        assert user is not None
        user.roles.append(await get_user_role(session, "ADMIN"))
        await session.commit()
    token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "correct-horse-battery-staple"},
        )
    ).json()["access_token"]
    return token


async def _create_job(client: AsyncClient, token: str, model: str = "test-model") -> dict:
    response = await client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": model},
        json={"model": model, "input": {"prompt": "private input"}},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_admin_boundary_and_bounded_inspection(app, client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/jobs")).status_code == 401
    user_token = await _register(client, "user@example.com")
    assert (
        await client.get("/api/v1/admin/jobs", headers={"Authorization": f"Bearer {user_token}"})
    ).status_code == 403

    admin_token = await _make_admin(app, client)
    first = await _create_job(client, user_token, "model-a")
    second = await _create_job(client, user_token, "model-b")
    headers = {"Authorization": f"Bearer {admin_token}"}
    listed = await client.get("/api/v1/admin/jobs?limit=1&offset=0", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    filtered = await client.get(f"/api/v1/admin/jobs?job_id={first['id']}", headers=headers)
    assert filtered.json()[0]["id"] == first["id"]
    assert second["id"] != first["id"]


@pytest.mark.asyncio
async def test_admin_detail_redacts_sensitive_values_and_cancel_is_audited(
    app, client: AsyncClient
) -> None:
    user_token = await _register(client, "owner@example.com")
    admin_token = await _make_admin(app, client)
    job = await _create_job(client, user_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    detail = await client.get(f"/api/v1/admin/jobs/{job['id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert "input" not in body
    assert "configuration" not in body
    assert body["dispatches"]

    cancelled = await client.post(f"/api/v1/admin/jobs/{job['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "CANCEL_REQUESTED"
    async with app.state.session_factory() as session:
        audit = await session.scalar(
            select(AuditLog)
            .where(AuditLog.event_type == AuditEventType.ADMIN_JOB_CANCELLED)
            .order_by(AuditLog.created_at.desc())
        )
        assert audit is not None
        assert audit.actor_user_id is not None
        assert audit.context["target_job_id"] == job["id"]
        assert "private input" not in str(audit.context)

    repeated = await client.post(f"/api/v1/admin/jobs/{job['id']}/cancel", headers=headers)
    assert repeated.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_cancel_terminal_job(app, client: AsyncClient) -> None:
    admin_token = await _make_admin(app, client)
    user_token = await _register(client, "terminal-owner@example.com")
    job = await _create_job(client, user_token, "terminal-model")
    async with app.state.session_factory() as session:
        from aetherflow.infrastructure.database.models import Job, JobState

        record = await session.get(Job, UUID(job["id"]))
        assert record is not None
        record.state = JobState.SUCCEEDED
        await session.commit()
    response = await client.post(
        f"/api/v1/admin/jobs/{job['id']}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
