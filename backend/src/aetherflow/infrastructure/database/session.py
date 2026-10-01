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
    engine_options: dict[str, object] = {
        "echo": settings.debug,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if not settings.database_url.startswith("sqlite+aiosqlite://"):
        engine_options.update(
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_recycle=settings.database_pool_recycle_seconds,
        )
    return create_async_engine(settings.database_url, **engine_options)


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
