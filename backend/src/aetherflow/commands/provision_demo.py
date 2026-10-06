"""Provision an explicitly enabled, read-only recruiter demo account."""

import asyncio
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aetherflow.auth.passwords import hash_password
from aetherflow.auth.service import DEMO_EMAIL, get_user_role, write_audit
from aetherflow.config.settings import get_settings
from aetherflow.infrastructure.database.models import (
    ApiKey,
    AuditEventType,
    Job,
    JobState,
    OutboxDispatch,
    User,
    UserStatus,
)
from aetherflow.infrastructure.database.session import create_engine, create_session_factory
from aetherflow.jobs.schemas import JobCreateRequest
from aetherflow.jobs.service import cancel_job, submit_job

PROVISIONING_REQUEST_ID = "trusted-demo-provisioner"
FIXTURE_SCHEDULE = datetime(2099, 1, 1, tzinfo=UTC)


async def provision_demo(session: AsyncSession, *, enabled: bool, password: str | None) -> User:
    if not enabled:
        raise RuntimeError("Demo provisioning is disabled; set AETHERFLOW_DEMO_ENABLED=true.")

    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.email == DEMO_EMAIL)
    )
    demo_role = await get_user_role(session, "DEMO")
    if user is None:
        if password is None:
            raise RuntimeError("AETHERFLOW_DEMO_PASSWORD is required for first-time provisioning.")
        if not 12 <= len(password) <= 128 or not password.strip():
            raise RuntimeError("AETHERFLOW_DEMO_PASSWORD must satisfy the account password policy.")
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE,
        )
        user.roles.append(demo_role)
        session.add(user)
        await session.flush()
        await write_audit(
            session,
            AuditEventType.REGISTRATION,
            actor_user_id=user.id,
            request_id=PROVISIONING_REQUEST_ID,
            success=True,
            source="trusted_cli",
            context={"account_type": "demo"},
        )
        await session.commit()
        await session.refresh(user, attribute_names=["roles"])
    elif user.status != UserStatus.ACTIVE or {role.name for role in user.roles} != {"DEMO"}:
        raise RuntimeError(
            "The reserved demo email belongs to a different or inactive identity; no changes made."
        )

    existing_key = await session.scalar(select(ApiKey.id).where(ApiKey.user_id == user.id).limit(1))
    if existing_key is not None:
        raise RuntimeError(
            "The demo account has API keys; revoke them before provisioning fixtures."
        )

    scheduled = await _ensure_fixture(
        session,
        user,
        key="aetherflow-demo-scheduled-v1",
        label="Future scheduled demo fixture",
        prompt="Seeded demonstration record. No provider execution is claimed.",
    )
    cancel_requested = await _ensure_fixture(
        session,
        user,
        key="aetherflow-demo-cancel-request-v1",
        label="Cancellation-request demo fixture",
        prompt="Seeded demonstration record. No provider execution is claimed.",
    )
    if cancel_requested.state == JobState.ACCEPTED:
        cancel_requested = await cancel_job(
            session,
            user,
            cancel_requested.id,
            request_id=PROVISIONING_REQUEST_ID,
        )
    if scheduled.state != JobState.ACCEPTED or cancel_requested.state != JobState.CANCEL_REQUESTED:
        raise RuntimeError(
            "A demo fixture has an unexpected lifecycle state; no state was overwritten."
        )

    dispatch = await session.scalar(
        select(OutboxDispatch.id)
        .where(OutboxDispatch.job_id.in_([scheduled.id, cancel_requested.id]))
        .limit(1)
    )
    if dispatch is not None:
        raise RuntimeError("A demo fixture unexpectedly has a dispatch intent.")
    return user


async def _ensure_fixture(
    session: AsyncSession,
    user: User,
    *,
    key: str,
    label: str,
    prompt: str,
) -> Job:
    payload = JobCreateRequest(
        model="demo-fixture",
        input={"prompt": prompt},
        metadata={"demo_fixture": True, "demo_label": label},
        schedule_at=FIXTURE_SCHEDULE,
    )
    job, _ = await submit_job(
        session,
        user,
        payload,
        idempotency_key=key,
        request_id=PROVISIONING_REQUEST_ID,
    )
    return job


async def _run() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            await provision_demo(
                session,
                enabled=settings.demo_enabled,
                password=os.environ.get("AETHERFLOW_DEMO_PASSWORD"),
            )
        print(f"Read-only demo account is ready: {DEMO_EMAIL}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
