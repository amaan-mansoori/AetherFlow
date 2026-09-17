"""Database session lifecycle tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aetherflow.infrastructure.database.session import create_session_factory, get_db_session


@pytest.mark.asyncio
async def test_session_dependency_opens_and_closes(database_engine: AsyncEngine) -> None:
    factory = create_session_factory(database_engine)
    generator = get_db_session(factory)
    session = await anext(generator)
    assert isinstance(session, AsyncSession)
    result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
    await generator.aclose()
    assert session.is_active is True
