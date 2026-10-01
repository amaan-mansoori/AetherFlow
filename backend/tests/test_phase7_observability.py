"""Phase 7 metrics and operational endpoint tests."""

import re

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint_is_prometheus_compatible_and_bounded(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "# TYPE aetherflow_http_requests_total counter" in body
    assert "# TYPE aetherflow_http_request_duration_seconds histogram" in body
    assert "job_id" not in body
    assert "request_id" not in body
    assert not re.search(r'path="[^"]*/[0-9a-f-]{20,}"', body)


@pytest.mark.asyncio
async def test_http_metrics_record_normalized_route_and_status_class(client: AsyncClient) -> None:
    await client.get("/health/live")
    await client.get("/missing-resource")
    body = (await client.get("/metrics")).text
    assert 'method="GET",route="/health/live",status_class="2xx"' in body
    assert 'method="GET",route="unmatched",status_class="4xx"' in body


@pytest.mark.asyncio
async def test_readiness_and_liveness_remain_distinct(client: AsyncClient) -> None:
    assert (await client.get("/health/live")).json() == {"status": "alive"}
    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["database"] == "ready"
