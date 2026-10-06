"""Optional bounded pagination for per-job console history."""

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select

from aetherflow.infrastructure.database.models import JobAttempt


async def _access_token(client: AsyncClient) -> str:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": "phase14@example.com", "password": "correct-horse-battery-staple"},
    )
    assert registered.status_code == 201
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "phase14@example.com", "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_job_history_optional_pagination_preserves_default(client: AsyncClient, app) -> None:
    token = await _access_token(client)
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "phase14-history-pagination",
    }
    created = await client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"model": "console-test", "input": {"prompt": "pagination"}},
    )
    assert created.status_code == 201
    job_id = created.json()["id"]
    cancelled = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
    assert cancelled.status_code == 200

    all_events = await client.get(f"/api/v1/jobs/{job_id}/events", headers=headers)
    assert all_events.status_code == 200
    assert len(all_events.json()) == 2
    first_event = await client.get(
        f"/api/v1/jobs/{job_id}/events?limit=1&offset=0", headers=headers
    )
    second_event = await client.get(
        f"/api/v1/jobs/{job_id}/events?limit=1&offset=1", headers=headers
    )
    assert len(first_event.json()) == len(second_event.json()) == 1
    assert first_event.json()[0]["id"] != second_event.json()[0]["id"]

    async with app.state.session_factory() as session:
        for attempt_number in (1, 2):
            session.add(
                JobAttempt(
                    job_id=UUID(job_id),
                    attempt_number=attempt_number,
                    status="FAILED",
                )
            )
        await session.commit()
        saved = list(
            (
                await session.scalars(select(JobAttempt).where(JobAttempt.job_id == UUID(job_id)))
            ).all()
        )
        assert len(saved) == 2

    all_attempts = await client.get(f"/api/v1/jobs/{job_id}/attempts", headers=headers)
    page = await client.get(f"/api/v1/jobs/{job_id}/attempts?limit=1&offset=1", headers=headers)
    assert len(all_attempts.json()) == 2
    assert len(page.json()) == 1
    assert page.json()[0]["attempt_number"] == 2
