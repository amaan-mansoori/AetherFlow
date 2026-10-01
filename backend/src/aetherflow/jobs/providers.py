"""Provider adapters and deterministic execution-provider selection."""

import asyncio
from collections.abc import Mapping
from time import perf_counter
from typing import Protocol

from aetherflow.config.settings import Settings
from aetherflow.jobs.execution import (
    ExecutionFailure,
    ExecutionFailureKind,
    ExecutionOutcome,
    ExecutionRequest,
    JobExecutor,
)
from aetherflow.observability.metrics import METRICS


class ProviderAdapter(Protocol):
    """Provider-specific execution boundary."""

    @property
    def name(self) -> str:
        """Return the stable provider identifier."""
        ...

    def supports_model(self, model: str) -> bool:
        """Return whether this provider accepts the model identifier."""
        ...

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        """Execute one request and return normalized output."""
        ...


class ProviderRegistry:
    """Deterministic registry mapping provider identifiers to adapters."""

    def __init__(self, adapters: Mapping[str, ProviderAdapter] | None = None) -> None:
        self._adapters = dict(adapters or {})

    def register(self, adapter: ProviderAdapter) -> None:
        if not adapter.name.strip():
            raise ValueError("provider name must not be blank")
        if adapter.name in self._adapters:
            raise ValueError(f"provider already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def resolve(self, provider: str, model: str) -> ProviderAdapter:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise ExecutionFailure(
                ExecutionFailureKind.PERMANENT_PROVIDER,
                f"Unsupported provider: {provider}.",
                provider=provider,
            )
        if not adapter.supports_model(model):
            raise ExecutionFailure(
                ExecutionFailureKind.PERMANENT_PROVIDER,
                f"Unsupported model '{model}' for provider '{provider}'.",
                provider=provider,
            )
        return adapter


class ProviderExecutor(JobExecutor):
    """Resolve a provider and normalize its adapter failures."""

    def __init__(self, registry: ProviderRegistry, default_provider: str = "mock") -> None:
        if not default_provider.strip():
            raise ValueError("default_provider must not be blank")
        self._registry = registry
        self._default_provider = default_provider

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        configured_provider = request.configuration.get("provider", self._default_provider)
        if not isinstance(configured_provider, str) or not configured_provider.strip():
            raise ExecutionFailure(
                ExecutionFailureKind.PERMANENT_PROVIDER,
                "Provider configuration must be a non-empty string.",
            )
        provider = configured_provider.strip()
        adapter = self._registry.resolve(provider, request.model)
        started = perf_counter()
        METRICS.inc("aetherflow_provider_executions_total", provider=provider)
        try:
            outcome = await adapter.execute(request)
        except ExecutionFailure as exc:
            METRICS.inc(
                "aetherflow_provider_failures_total",
                provider=provider,
                failure_category=exc.kind.value,
            )
            METRICS.observe(
                "aetherflow_provider_execution_duration_seconds",
                perf_counter() - started,
                provider=provider,
            )
            if exc.provider is None:
                raise ExecutionFailure(exc.kind, exc.message, provider=provider) from exc
            raise
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            METRICS.inc(
                "aetherflow_provider_failures_total",
                provider=provider,
                failure_category=ExecutionFailureKind.TRANSIENT_PROVIDER.value,
            )
            METRICS.observe(
                "aetherflow_provider_execution_duration_seconds",
                perf_counter() - started,
                provider=provider,
            )
            raise ExecutionFailure(
                ExecutionFailureKind.TRANSIENT_PROVIDER,
                "Provider execution failed.",
                provider=provider,
            ) from exc
        if (
            not isinstance(outcome, ExecutionOutcome)
            or not isinstance(outcome.output, dict)
            or not isinstance(outcome.schema_version, str)
            or not outcome.schema_version.strip()
        ):
            METRICS.inc(
                "aetherflow_provider_failures_total",
                provider=provider,
                failure_category=ExecutionFailureKind.VALIDATION.value,
            )
            METRICS.observe(
                "aetherflow_provider_execution_duration_seconds",
                perf_counter() - started,
                provider=provider,
            )
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "Provider returned an invalid normalized outcome.",
                provider=provider,
            )
        if outcome.usage is not None and not isinstance(outcome.usage, dict):
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "Provider returned invalid usage metadata.",
                provider=provider,
            )
        METRICS.inc("aetherflow_provider_successes_total", provider=provider)
        METRICS.observe(
            "aetherflow_provider_execution_duration_seconds",
            perf_counter() - started,
            provider=provider,
        )
        return (
            outcome
            if outcome.provider == provider
            else ExecutionOutcome(
                output=outcome.output,
                usage=outcome.usage,
                schema_version=outcome.schema_version,
                provider=provider,
                finish_reason=outcome.finish_reason,
            )
        )


class MockProviderAdapter:
    """Deterministic local provider for development, tests, and CI."""

    name = "mock"

    def supports_model(self, model: str) -> bool:
        return bool(model.strip())

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        mode = request.configuration.get("mock_failure")
        if mode is not None:
            if not isinstance(mode, str):
                raise ExecutionFailure(
                    ExecutionFailureKind.VALIDATION,
                    "mock_failure must be a string.",
                    provider=self.name,
                )
            failures = {
                "validation": ExecutionFailureKind.VALIDATION,
                "authentication": ExecutionFailureKind.AUTHENTICATION,
                "rate_limit": ExecutionFailureKind.RATE_LIMIT,
                "timeout": ExecutionFailureKind.TIMEOUT,
                "transient": ExecutionFailureKind.TRANSIENT_PROVIDER,
                "permanent": ExecutionFailureKind.PERMANENT_PROVIDER,
                "cancellation": ExecutionFailureKind.CANCELLATION,
            }
            failure_kind = failures.get(mode)
            if failure_kind is None:
                raise ExecutionFailure(
                    ExecutionFailureKind.VALIDATION,
                    f"Unsupported mock failure mode: {mode}.",
                    provider=self.name,
                )
            raise ExecutionFailure(
                failure_kind,
                f"Deterministic mock failure: {mode}.",
                provider=self.name,
            )

        prompt = request.input.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ExecutionFailure(
                ExecutionFailureKind.VALIDATION,
                "structured_inference requires a non-empty string prompt.",
                provider=self.name,
            )
        return ExecutionOutcome(
            output={"text": prompt},
            provider=self.name,
            finish_reason="stop",
        )


def create_default_provider_executor(settings: Settings) -> ProviderExecutor:
    """Build the configured local provider executor without loading secrets."""

    registry = ProviderRegistry()
    registry.register(MockProviderAdapter())
    return ProviderExecutor(registry, default_provider=settings.provider_default)
