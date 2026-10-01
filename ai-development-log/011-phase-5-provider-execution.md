# Phase 5 — Provider Execution Boundary

## Scope decision

Phase 5 is intentionally limited to the provider execution layer needed after
Phase 4: a provider registry, normalized provider adapter contract,
deterministic mock execution, explicit provider failure categories, worker
timeouts, and credential-safe configuration. Redis, scheduling, external
provider transport, execution retries, frontend, and deployment remain out of
scope.

## Why this scope

Phase 4 made dispatch durable and restart-safe, but the worker still required
an externally supplied executor and had no provider selection or timeout
normalization. This boundary is the smallest cohesive step toward useful AI
execution without changing the outbox, Kafka, state machine, or persistence
authority.

## Architecture and implementation

`Worker -> JobExecutor -> ProviderExecutor -> ProviderRegistry ->
ProviderAdapter`. `MockProviderAdapter` is deterministic and credential-free.
Provider selection uses job configuration's non-secret `provider` value or the
runtime `provider_default` setting. Provider adapters return the existing
`ExecutionOutcome`; the provider boundary validates normalized output, while
the worker persists provider and usage metadata on the attempt and keeps
provider I/O outside database transactions.

The worker maps timeout to `TIMEOUT` and provider adapters normalize validation,
authentication, rate-limit, timeout, transient, permanent, cancellation, and
unexpected categories. No automatic execution retry was added.

## Verification and limitations

The Phase 5 tests cover registry resolution, deterministic success/failure,
worker persistence, timeout durability, and credential rejection. No migration
was required because existing configuration and attempt fields are sufficient.
External provider, PostgreSQL, and Kafka verification remain unavailable unless
those services are explicitly provided.
