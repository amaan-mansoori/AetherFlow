"""Deterministic tests for the OpenAI-compatible provider adapter."""

from uuid import UUID

import httpx
import pytest

from aetherflow.jobs.execution import ExecutionFailure, ExecutionFailureKind, ExecutionRequest
from aetherflow.jobs.openai import OpenAICompatibleAdapter


def request(configuration: dict[str, object] | None = None) -> ExecutionRequest:
    return ExecutionRequest(
        UUID(int=1),
        "structured_inference",
        "test-model",
        {"prompt": "hello"},
        configuration or {},
        5,
        {},
    )


def adapter(handler) -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(
        "test-secret-that-is-never-logged",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://provider.test/v1",
            headers={"Authorization": "Bearer test-secret-that-is-never-logged"},
        ),
    )


@pytest.mark.asyncio
async def test_openai_adapter_normalizes_success_and_usage() -> None:
    async def handler(call: httpx.Request) -> httpx.Response:
        assert call.url.path == "/v1/chat/completions"
        assert call.headers["authorization"] == "Bearer test-secret-that-is-never-logged"
        body = httpx.Request("POST", call.url)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            },
            request=body,
        )

    provider = adapter(handler)
    outcome = await provider.execute(request({"temperature": 0.2, "max_tokens": 20}))
    assert outcome.output == {"text": "answer"}
    assert outcome.usage == {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}
    assert outcome.provider == "openai"
    await provider._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (401, ExecutionFailureKind.AUTHENTICATION),
        (429, ExecutionFailureKind.RATE_LIMIT),
        (500, ExecutionFailureKind.TRANSIENT_PROVIDER),
        (400, ExecutionFailureKind.PERMANENT_PROVIDER),
    ],
)
async def test_openai_adapter_maps_http_failures(status: int, kind: ExecutionFailureKind) -> None:
    async def handler(call: httpx.Request) -> httpx.Response:
        return httpx.Response(status, request=call)

    provider = adapter(handler)
    with pytest.raises(ExecutionFailure) as failure:
        await provider.execute(request())
    assert failure.value.kind == kind
    assert "test-secret" not in failure.value.message
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_openai_adapter_maps_timeout_without_retry_loop() -> None:
    async def handler(call: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timeout", request=call)

    provider = adapter(handler)
    with pytest.raises(ExecutionFailure) as failure:
        await provider.execute(request())
    assert failure.value.kind == ExecutionFailureKind.TIMEOUT
    await provider._client.aclose()


@pytest.mark.asyncio
async def test_openai_adapter_rejects_malformed_response_and_configuration() -> None:
    async def handler(call: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []}, request=call)

    provider = adapter(handler)
    with pytest.raises(ExecutionFailure) as malformed:
        await provider.execute(request())
    assert malformed.value.kind == ExecutionFailureKind.VALIDATION
    with pytest.raises(ExecutionFailure) as unsupported:
        await provider.execute(request({"top_p": 0.5}))
    assert unsupported.value.kind == ExecutionFailureKind.VALIDATION
    await provider._client.aclose()


def test_openai_provider_requires_key_when_selected() -> None:
    from aetherflow.config.settings import Settings

    with pytest.raises(ValueError, match="provider_openai_api_key"):
        Settings(
            _env_file=None,
            environment="test",
            database_url="sqlite+aiosqlite:///:memory:",
            jwt_secret_key="x" * 40,
            provider_default="openai",
        )
