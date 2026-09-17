"""FastAPI dependency adapters."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_request_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Resolve the application-owned session factory for one request."""

    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
