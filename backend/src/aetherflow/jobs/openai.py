"""OpenAI-compatible provider adapter with normalized failure handling."""

from collections.abc import Mapping

import httpx

from aetherflow.jobs.execution import (
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionOutcome,
    ExecutionRequest,
)


class OpenAICompatibleAdapter:
    """Call a chat-completions compatible endpoint without provider retries."""

    name = "openai"
    _allowed_configuration = frozenset({"provider", "temperature", "max_tokens"})

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        max_connections: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key must not be blank")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections,
            ),
        )

    def supports_model(self, model: str) -> bool:
        return bool(model.strip())

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        prompt = request.input.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "structured_inference requires a non-empty string prompt.",
                provider=self.name,
            )
        unsupported = set(request.configuration) - self._allowed_configuration
        if unsupported:
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "Unsupported provider configuration.",
                provider=self.name,
            )
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        for key in ("temperature", "max_tokens"):
            if key in request.configuration:
                value = request.configuration[key]
                if key == "temperature" and not isinstance(value, (int, float)):
                    raise ExecutionFailure(
                        ExecutionFailureKind.VALIDATION,
                        "temperature must be numeric.",
                        provider=self.name,
                    )
                if key == "max_tokens" and (
                    not isinstance(value, int) or isinstance(value, bool) or value < 1
                ):
                    raise ExecutionFailure(
                        ExecutionFailureKind.VALIDATION,
                        "max_tokens must be a positive integer.",
                        provider=self.name,
                    )
                payload[key] = value
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise ExecutionFailure(
                ExecutionFailureKind.TIMEOUT,
                "Provider request timed out.",
                provider=self.name,
            ) from exc
        except httpx.RequestError as exc:
            raise ExecutionFailure(
                ExecutionFailureKind.TRANSIENT_PROVIDER,
                "Provider request failed.",
                provider=self.name,
            ) from exc
        if response.status_code == 401 or response.status_code == 403:
            raise ExecutionFailure(
                ExecutionFailureKind.AUTHENTICATION,
                "Provider authentication failed.",
                provider=self.name,
            )
        if response.status_code == 429:
            raise ExecutionFailure(
                ExecutionFailureKind.RATE_LIMIT,
                "Provider rate limit reached.",
                provider=self.name,
            )
        if 500 <= response.status_code <= 599:
            raise ExecutionFailure(
                ExecutionFailureKind.TRANSIENT_PROVIDER,
                "Provider service is temporarily unavailable.",
                provider=self.name,
            )
        if 400 <= response.status_code <= 499:
            raise ExecutionFailure(
                ExecutionFailureKind.PERMANENT_PROVIDER,
                "Provider rejected the request.",
                provider=self.name,
            )
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "Provider returned a malformed response.",
                provider=self.name,
            ) from exc
        if not isinstance(content, str):
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "Provider returned invalid message content.",
                provider=self.name,
            )
        usage = _normalize_usage(body.get("usage"))
        finish_reason = body["choices"][0].get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            finish_reason = None
        return ExecutionOutcome(
            output={"text": content},
            usage=usage,
            provider=self.name,
            finish_reason=finish_reason,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _normalize_usage(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    normalized: dict[str, object] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        item = value.get(key)
        if isinstance(item, int) and not isinstance(item, bool) and item >= 0:
            normalized[key] = item
    return normalized or None
