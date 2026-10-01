"""Job domain, state machine, idempotency, and lifecycle tests."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from aetherflow.api.errors import ApiError
from aetherflow.infrastructure.database.models import JobState, User
from aetherflow.jobs.idempotency import compute_payload_fingerprint, validate_idempotency_key
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import (
    cancel_job,
    get_job,
    record_job_attempt,
    record_job_result,
    submit_job,
    transition_job_state,
)
from aetherflow.jobs.state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    can_transition,
    is_terminal_state,
    validate_transition,
)


async def create_user_and_get_token(client: AsyncClient, email: str = "jobuser@example.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery staple"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    return str(login.json()["access_token"])


def sample_job_payload(prompt: str = "Analyze sentiment") -> dict[str, Any]:
    return {
        "type": "structured_inference",
        "model": "mock-gpt",
        "input": {"prompt": prompt},
        "configuration": {"temperature": 0.2},
        "priority": 1,
        "timeout_seconds": 120,
        "retry_policy": {
            "max_attempts": 3,
            "initial_backoff_seconds": 1.0,
            "max_backoff_seconds": 30.0,
            "backoff_multiplier": 2.0,
            "jitter": True,
        },
        "metadata": {"trace_group": "sentiment-analysis"},
    }


# =========================================================================
# 1. State Machine Unit Tests
# =========================================================================


def test_state_machine_valid_transitions() -> None:
    for source_state, target_states in VALID_TRANSITIONS.items():
        for target in target_states:
            assert can_transition(source_state, target) is True
            validate_transition(source_state, target)


def test_state_machine_invalid_transitions() -> None:
    invalid_cases = [
        (JobState.ACCEPTED, JobState.RUNNING),
        (JobState.ACCEPTED, JobState.SUCCEEDED),
        (JobState.QUEUED, JobState.SUCCEEDED),
        (JobState.RUNNING, JobState.QUEUED),
        (JobState.RUNNING, JobState.ACCEPTED),
        (JobState.RETRY_SCHEDULED, JobState.RUNNING),
        (JobState.RETRY_SCHEDULED, JobState.SUCCEEDED),
        (JobState.CANCEL_REQUESTED, JobState.QUEUED),
        (JobState.CANCEL_REQUESTED, JobState.RUNNING),
    ]
    for source, target in invalid_cases:
        assert can_transition(source, target) is False
        with pytest.raises(ApiError) as exc_info:
            validate_transition(source, target)
        assert exc_info.value.code == "INVALID_STATE_TRANSITION"
        assert exc_info.value.status_code == 409


def test_state_machine_terminal_states() -> None:
    for terminal in TERMINAL_STATES:
        assert is_terminal_state(terminal) is True
        for any_target in JobState:
            with pytest.raises(ApiError) as exc_info:
                validate_transition(terminal, any_target)
            assert exc_info.value.code == "INVALID_STATE_TRANSITION"
            assert "terminal state" in exc_info.value.message


# =========================================================================
# 2. Idempotency Fingerprinting Unit Tests
# =========================================================================


def test_payload_fingerprinting_canonicalization() -> None:
    payload_a = {"b": 2, "a": 1, "nested": {"y": [1, 2], "x": True}}
    payload_b = {"a": 1, "nested": {"x": True, "y": [1, 2]}, "b": 2}
    assert compute_payload_fingerprint(payload_a) == compute_payload_fingerprint(payload_b)


def test_payload_fingerprinting_different_content() -> None:
    payload_a = {"prompt": "Hello"}
    payload_b = {"prompt": "World"}
    assert compute_payload_fingerprint(payload_a) != compute_payload_fingerprint(payload_b)


def test_validate_idempotency_key() -> None:
    assert validate_idempotency_key("  my-key-123  ") == "my-key-123"
    with pytest.raises(ApiError) as missing:
        validate_idempotency_key(None)
    assert missing.value.code == "VALIDATION_ERROR"
    with pytest.raises(ApiError) as blank:
        validate_idempotency_key("   ")
    assert blank.value.code == "VALIDATION_ERROR"
    with pytest.raises(ApiError) as too_long:
        validate_idempotency_key("k" * 129)
    assert too_long.value.code == "VALIDATION_ERROR"


# =========================================================================
# 3. Authentication & API Key Tests
# =========================================================================


@pytest.mark.asyncio
async def test_job_submission_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"Idempotency-Key": "unauth-key-1"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_job_submission_with_api_key(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "apikey-user@example.com")
    key_res = await client.post(
        "/api/v1/api-keys",
        json={"name": "job-submitter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    secret = key_res.json()["secret"]

    job_res = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"X-API-Key": secret, "Idempotency-Key": "apikey-job-1"},
    )
    assert job_res.status_code == 201
    assert job_res.json()["state"] == "ACCEPTED"


# =========================================================================
# 4. Job Creation & Validation Tests
# =========================================================================


@pytest.mark.asyncio
async def test_job_creation_success(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "creator@example.com")
    response = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "job-key-success"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "ACCEPTED"
    assert data["type"] == "structured_inference"
    assert data["model"] == "mock-gpt"
    assert data["priority"] == 1
    assert data["version"] == 1
    assert data["input"] == {"prompt": "Analyze sentiment"}
    assert data["configuration"] == {"temperature": 0.2}
    assert data["metadata"] == {"trace_group": "sentiment-analysis"}
    assert "password" not in response.text
    assert "secret" not in response.text


@pytest.mark.asyncio
async def test_job_creation_missing_idempotency_key(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "no-idem@example.com")
    response = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_job_creation_unknown_fields_rejected(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "unknown-fields@example.com")
    payload = sample_job_payload()
    payload["arbitrary_extra_field"] = "should-fail"
    response = await client.post(
        "/api/v1/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "extra-fields-key"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_job_creation_blank_model_rejected(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "blank-model@example.com")
    payload = sample_job_payload()
    payload["model"] = "   "
    response = await client.post(
        "/api/v1/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "blank-model-key"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# =========================================================================
# 5. Idempotency Behavior Tests
# =========================================================================


@pytest.mark.asyncio
async def test_idempotent_replay_returns_existing_job(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "idem-replay@example.com")
    payload = sample_job_payload("Identical prompt")

    res1 = await client.post(
        "/api/v1/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "replay-key"},
    )
    assert res1.status_code == 201
    job_id_1 = res1.json()["id"]

    res2 = await client.post(
        "/api/v1/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "replay-key"},
    )
    assert res2.status_code == 200
    assert res2.json()["id"] == job_id_1


@pytest.mark.asyncio
async def test_idempotency_key_reuse_with_different_payload_fails(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "idem-diff@example.com")

    res1 = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload("First payload"),
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "shared-key-1"},
    )
    assert res1.status_code == 201

    res2 = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload("Different second payload"),
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "shared-key-1"},
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert "different request" in res2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_idempotency_keys_are_scoped_per_user(client: AsyncClient) -> None:
    token1 = await create_user_and_get_token(client, "user1@example.com")
    token2 = await create_user_and_get_token(client, "user2@example.com")

    shared_key = "user-independent-key"
    res1 = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload("User 1 prompt"),
        headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": shared_key},
    )
    assert res1.status_code == 201
    job_1_id = res1.json()["id"]

    res2 = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload("User 2 prompt"),
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": shared_key},
    )
    assert res2.status_code == 201
    job_2_id = res2.json()["id"]

    assert job_1_id != job_2_id


# =========================================================================
# 6. Ownership & Multi-User Boundary Tests
# =========================================================================


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_job(client: AsyncClient) -> None:
    token1 = await create_user_and_get_token(client, "owner@example.com")
    token2 = await create_user_and_get_token(client, "intruder@example.com")

    res = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": "owner-job"},
    )
    job_id = res.json()["id"]

    # Owner can access
    owner_get = await client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert owner_get.status_code == 200

    # Intruder cannot access: must return 404 NOT_FOUND, not 403 (no leakage)
    intruder_get = await client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert intruder_get.status_code == 404
    assert intruder_get.json()["error"]["code"] == "NOT_FOUND"

    # Intruder cannot cancel: must return 404 NOT_FOUND
    intruder_cancel = await client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert intruder_cancel.status_code == 404
    assert intruder_cancel.json()["error"]["code"] == "NOT_FOUND"

    # Intruder cannot see events or attempts
    intruder_events = await client.get(
        f"/api/v1/jobs/{job_id}/events",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert intruder_events.status_code == 404
    intruder_attempts = await client.get(
        f"/api/v1/jobs/{job_id}/attempts",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert intruder_attempts.status_code == 404


@pytest.mark.asyncio
async def test_job_listing_is_scoped_to_authenticated_user(client: AsyncClient) -> None:
    token1 = await create_user_and_get_token(client, "lister1@example.com")
    token2 = await create_user_and_get_token(client, "lister2@example.com")

    # Create 2 jobs for user1
    for i in range(2):
        await client.post(
            "/api/v1/jobs",
            json=sample_job_payload(f"User 1 job {i}"),
            headers={"Authorization": f"Bearer {token1}", "Idempotency-Key": f"u1-job-{i}"},
        )
    # Create 1 job for user2
    await client.post(
        "/api/v1/jobs",
        json=sample_job_payload("User 2 job 0"),
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": "u2-job-0"},
    )

    list1 = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token1}"})
    assert list1.status_code == 200
    assert len(list1.json()) == 2

    list2 = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token2}"})
    assert list2.status_code == 200
    assert len(list2.json()) == 1


# =========================================================================
# 7. Cancellation & Event Lifecycle Tests
# =========================================================================


@pytest.mark.asyncio
async def test_cancellation_lifecycle(client: AsyncClient) -> None:
    token = await create_user_and_get_token(client, "canceler@example.com")
    res = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cancel-me-1"},
    )
    job_id = res.json()["id"]

    # Cancel job
    cancel_res = await client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["state"] == "CANCEL_REQUESTED"
    assert cancel_res.json()["version"] == 2

    # Repeated cancellation is idempotent
    cancel_repeat = await client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cancel_repeat.status_code == 200
    assert cancel_repeat.json()["state"] == "CANCEL_REQUESTED"

    # Events endpoint shows JOB_ACCEPTED and CANCEL_REQUESTED
    events_res = await client.get(
        f"/api/v1/jobs/{job_id}/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) == 2
    assert events[0]["event_type"] == "JOB_ACCEPTED"
    assert events[1]["event_type"] == "CANCEL_REQUESTED"


# =========================================================================
# 8. Domain Service Direct Tests (Attempts, Results, State Transitions)
# =========================================================================


@pytest.mark.asyncio
async def test_domain_state_transitions_and_concurrency_versioning(app) -> None:
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(
            session, "domainuser@example.com", "correct horse battery staple", None
        )

        payload = JobCreateRequest(
            type="structured_inference",
            model="mock-gpt",
            input={"prompt": "Domain test"},
        )
        job, is_new = await submit_job(session, user, payload, "domain-key-1")
        assert is_new is True
        assert job.state == JobState.ACCEPTED
        assert job.version == 1
        job_id = job.id

        # ACCEPTED -> QUEUED
        job = await transition_job_state(session, job_id, JobState.QUEUED, "dispatcher")
        assert job.state == JobState.QUEUED
        assert job.version == 2

        # QUEUED -> RUNNING
        job = await transition_job_state(session, job_id, JobState.RUNNING, "worker-1")
        assert job.state == JobState.RUNNING
        assert job.version == 3

        # Record attempt
        attempt = await record_job_attempt(
            session,
            job_id,
            attempt_number=1,
            status="RUNNING",
            worker_id="worker-1",
            provider="mock-provider",
            model="mock-gpt",
        )
        assert attempt.attempt_number == 1
        assert attempt.status == "RUNNING"

        # Duplicate attempt number rejected
        with pytest.raises(ApiError) as exc:
            await record_job_attempt(
                session,
                job_id,
                attempt_number=1,
                status="RUNNING",
            )
        assert exc.value.code == "CONFLICT"

        # Record result
        result = await record_job_result(
            session,
            job_id,
            output={"classification": "positive", "confidence": 0.98},
            usage={"prompt_tokens": 5, "completion_tokens": 10},
        )
        assert result.output == {"classification": "positive", "confidence": 0.98}

        # Duplicate result rejected
        with pytest.raises(ApiError) as exc:
            await record_job_result(session, job_id, output={"another": "result"})
        assert exc.value.code == "CONFLICT"

        # RUNNING -> SUCCEEDED
        job = await transition_job_state(session, job_id, JobState.SUCCEEDED, "worker-1")
        assert job.state == JobState.SUCCEEDED
        assert job.version == 4

        # Cannot cancel terminal job
        with pytest.raises(ApiError) as exc:
            await cancel_job(session, user, job_id)
        assert exc.value.code == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_state_transition_rejects_stale_expected_version(app) -> None:
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(
            session, "stale-version@example.com", "correct horse battery staple", None
        )
        job, _ = await submit_job(
            session,
            user,
            JobCreateRequest(model="mock-gpt", input={"prompt": "stale version"}),
            "stale-version-key",
        )
        job = await transition_job_state(session, job.id, JobState.QUEUED, "dispatcher")

        with pytest.raises(ApiError) as exc:
            await transition_job_state(
                session,
                job.id,
                JobState.CANCEL_REQUESTED,
                "user:stale-version",
                expected_version=1,
            )
        assert exc.value.code == "CONFLICT"

        refreshed = await get_job(session, user, job.id)
        assert refreshed.state == JobState.QUEUED
        assert refreshed.version == 2


@pytest.mark.asyncio
async def test_attempt_and_result_require_execution_state(app) -> None:
    from aetherflow.auth.service import register_user

    async with app.state.session_factory() as session:
        user = await register_user(
            session, "execution-state@example.com", "correct horse battery staple", None
        )
        job, _ = await submit_job(
            session,
            user,
            JobCreateRequest(model="mock-gpt", input={"prompt": "state guard"}),
            "execution-state-key",
        )

        with pytest.raises(ApiError) as attempt_error:
            await record_job_attempt(session, job.id, 1, "RUNNING")
        assert attempt_error.value.code == "INVALID_STATE_TRANSITION"

        with pytest.raises(ApiError) as result_error:
            await record_job_result(session, job.id, {"classification": "positive"})
        assert result_error.value.code == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_admin_can_access_any_job(app, client: AsyncClient) -> None:
    from sqlalchemy.orm import selectinload

    # Create user job
    user_token = await create_user_and_get_token(client, "regular-user@example.com")
    res = await client.post(
        "/api/v1/jobs",
        json=sample_job_payload(),
        headers={"Authorization": f"Bearer {user_token}", "Idempotency-Key": "regular-job"},
    )
    job_id = res.json()["id"]

    # Promote an admin user in the database
    _ = await create_user_and_get_token(client, "admin-user@example.com")
    async with app.state.session_factory() as session:
        from aetherflow.auth.service import get_user_role

        admin_user = await session.scalar(
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == "admin-user@example.com")
        )
        assert admin_user is not None
        admin_role = await get_user_role(session, "ADMIN")
        admin_user.roles.append(admin_role)
        await session.commit()

    # Re-login to get token with ADMIN role
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin-user@example.com", "password": "correct horse battery staple"},
    )
    new_admin_token = admin_login.json()["access_token"]

    # Admin can inspect regular user's job
    admin_get = await client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": f"Bearer {new_admin_token}"},
    )
    assert admin_get.status_code == 200
    assert admin_get.json()["id"] == job_id
