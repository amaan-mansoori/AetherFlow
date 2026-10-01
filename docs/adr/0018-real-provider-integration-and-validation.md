# ADR-0018: Real Provider Integration and Validation

## Status

Accepted — Phase 9.

## Decision

AetherFlow adds one OpenAI-compatible chat-completions adapter behind the
existing `ProviderAdapter` and `ProviderExecutor` boundary. Only the worker
constructs the provider client. The API does not initialize provider clients.
The adapter uses a reusable bounded async HTTP client, configured timeout, and
no automatic provider retry. Phase 6 remains the single retry authority.

Provider credentials are environment configuration only. Job configuration may
select `provider`, `temperature`, and `max_tokens`, but credentials and
arbitrary provider fields are rejected or unavailable. Responses are reduced to
the existing normalized output, usage, schema version, provider, and finish
reason fields.

HTTP failures map to the existing failure taxonomy: 401/403 authentication,
429 rate limit, timeouts network timeout, 5xx transient provider, other 4xx
permanent provider, and malformed success payload validation.

## Validation

Deterministic unit tests use `httpx.MockTransport`. Real provider and
PostgreSQL/Kafka/Docker end-to-end validation is reported only when those
dependencies and credentials are actually available.

## Consequences

The adapter is replaceable and does not leak provider response types into the
domain. External provider calls remain at-least-once and may be repeated by
durable execution retry. Provider credentials require external secret
management in production.
