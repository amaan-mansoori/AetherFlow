# ADR-0014: Provider Execution Boundary

**Status:** Accepted  
**Date:** 2026-10-02

## Decision

Phase 5 introduces a provider-independent execution boundary:

```text
Worker -> JobExecutor -> ProviderExecutor -> ProviderRegistry -> ProviderAdapter
```

The registry resolves a non-secret provider identifier from job configuration,
falling back to the environment-configured default. The deterministic mock
adapter is the only built-in adapter in this milestone. It validates the
structured inference input and returns the existing normalized execution
contract. The worker enforces the durable job timeout outside database
transactions and persists normalized provider/failure metadata on attempts.

Provider credentials are runtime configuration only. Job schemas reject
credential-like configuration keys rather than persisting secrets.

## Rationale

Phase 4 established durable dispatch and worker recovery but deliberately left
provider behavior deferred. This boundary makes execution useful locally and
keeps provider-specific SDKs, credentials, errors, and response formats out of
the worker and domain services. A deterministic mock preserves reproducible
tests and local operation without external cost or availability.

## Consequences

Provider failures are classified but are not automatically retried. Dispatch
retry remains an outbox concern; execution retry requires a separate durable
retry-dispatch design. No external provider is claimed as implemented or
verified, and no exactly-once execution guarantee is introduced.
