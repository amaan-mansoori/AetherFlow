"""Grant ADMIN to an existing account through a trusted operator command."""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aetherflow.auth.service import get_user_role, normalize_email, write_audit
from aetherflow.config.settings import get_settings
from aetherflow.infrastructure.database.models import AuditEventType, User, UserStatus
from aetherflow.infrastructure.database.session import create_engine, create_session_factory


async def grant_admin(session: AsyncSession, email: str) -> bool:
    normalized_email = normalize_email(email)
    user = await session.scalar(
        select(User).options(selectinload(User.roles)).where(User.email == normalized_email)
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise RuntimeError("An active registered account with that email was not found.")
    role_names = {role.name for role in user.roles}
    if "DEMO" in role_names:
        raise RuntimeError("A demo identity cannot be promoted to administrator.")
    if "ADMIN" in role_names:
        return False

    user.roles.append(await get_user_role(session, "ADMIN"))
    await write_audit(
        session,
        AuditEventType.ROLE_ASSIGNED,
        actor_user_id=None,
        request_id=None,
        success=True,
        source="trusted_cli",
        context={"target_user_id": str(user.id), "role": "ADMIN"},
    )
    await session.commit()
    return True


async def _run(email: str) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with create_session_factory(engine)() as session:
            changed = await grant_admin(session, email)
        message = (
            "Administrator role granted." if changed else "Account is already an administrator."
        )
        print(message)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email address of an existing registered account")
    args = parser.parse_args()
    asyncio.run(_run(args.email))


if __name__ == "__main__":
    main()
