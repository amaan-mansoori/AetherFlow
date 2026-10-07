"""Application and HTTP foundation tests."""

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient

from aetherflow.api.errors import validation_error_handler
from aetherflow.config.settings import Settings
from aetherflow.main import create_app


@pytest.mark.asyncio
async def test_application_starts(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_liveness_does_not_require_database(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_with_database(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ready"}


@pytest.mark.asyncio
async def test_readiness_returns_not_ready_when_database_is_unavailable() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            database_url="sqlite+aiosqlite:///C:/path-that-does-not-exist/aetherflow.db",
            logging_level="WARNING",
        )
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_request_id_is_generated_and_returned(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.headers["x-request-id"].startswith("req_")


@pytest.mark.asyncio
async def test_request_id_is_propagated(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "client.request-123"})
    assert response.headers["x-request-id"] == "client.request-123"


@pytest.mark.asyncio
async def test_invalid_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "bad value\n"})
    assert response.headers["x-request-id"].startswith("req_")


@pytest.mark.asyncio
async def test_cors_allows_configured_api_key_and_delete_requests(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/api-keys/example",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "X-API-Key" in response.headers["access-control-allow-headers"]


@pytest.mark.asyncio
async def test_not_found_uses_error_contract(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")
    body = response.json()["error"]
    assert response.status_code == 404
    assert body["code"] == "NOT_FOUND"
    assert body["request_id"] == response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_validation_error_uses_error_contract() -> None:
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    exception = RequestValidationError(
        [{"type": "missing", "loc": ("body", "name"), "msg": "Field required", "input": {}}]
    )
    response = await validation_error_handler(request, exception)
    assert response.status_code == 400
    assert response.body is not None
    assert b'"code":"VALIDATION_ERROR"' in response.body
