"""Shared isolated test fixtures."""

import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from aetherflow.config.settings import Settings
from aetherflow.infrastructure.database.base import Base
from aetherflow.infrastructure.database.models import Role
from aetherflow.infrastructure.database.session import create_engine

os.environ.setdefault("AETHERFLOW_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AETHERFLOW_JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")

from aetherflow.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        cors_origins=["http://localhost:3000"],
        logging_level="WARNING",
    )


@pytest.fixture
async def database_engine(test_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(test_settings)
    yield engine
    await engine.dispose()


@pytest.fixture
async def app(test_settings: Settings) -> AsyncIterator[FastAPI]:
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        async with app.state.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with app.state.session_factory() as session:
            session.add_all([Role(name="USER"), Role(name="ADMIN"), Role(name="DEMO")])
            await session.commit()
        yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
