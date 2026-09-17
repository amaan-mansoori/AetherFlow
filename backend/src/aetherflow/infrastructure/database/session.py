"""Async SQLAlchemy engine and session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aetherflow.config.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create a pooled engine for PostgreSQL or a test-compatible database URL."""

    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite+aiosqlite://"):
        connect_args["check_same_thread"] = False
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield one request-scoped session and always close it."""

    async with session_factory() as session:
        yield session
