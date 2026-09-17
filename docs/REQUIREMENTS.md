# Requirements

**Status:** Architecture / Specification Phase

## Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Authenticate users with email/password and JWT access tokens. | Must |
| FR-002 | Enforce `USER` and `ADMIN` authorization boundaries. | Must |
| FR-003 | Allow users to create, revoke, list metadata for, and use API keys; raw secrets are shown once only. | Must |
| FR-004 | Accept a structured inference job with type, model, input, configuration, priority, timeout, retry policy, metadata, and idempotency key. | Must |
| FR-005 | Persist a job before asynchronous dispatch. | Must |
| FR-006 | Support the documented explicit job state machine. | Must |
| FR-007 | Execute jobs through independently runnable workers using at-least-once delivery. | Must |
| FR-008 | Persist one attempt record for every execution attempt. | Must |
| FR-009 | Validate structured AI output before accepting a result. | Must |
| FR-010 | Support bounded retries, exponential backoff, jitter, retry budgets, and dead-letter handling. | Must |
| FR-011 | Support cancellation requests with honest provider-cancellation semantics. | Must |
| FR-012 | Enforce idempotency per authenticated principal and key, including concurrent requests and payload mismatch rejection. | Must |
| FR-013 | Apply configurable user, API, and job-submission rate limits. | Must |
| FR-014 | Expose job, attempt, result, worker, queue, audit, and operational data according to role. | Must |
| FR-015 | Emit structured logs, traces, request IDs, correlation IDs, and real metrics. | Must |
| FR-016 | Provide a professional console with the approved primary screens and honest empty states. | Must |

## Non-functional requirements

- Security: least privilege, secret redaction, validated input, parameterized persistence, no arbitrary command execution.
- Reliability: explicit state transitions, durable state before dispatch, restart-safe workers, at-least-once duplicate handling.
- Operability: health/readiness probes, actionable metrics, runbooks, failure matrix, and controlled deployment.
- Testability: deterministic mock provider, unit/integration/API/E2E/load/security test strategy.
- Portability: local Docker Compose and reproducible Kubernetes deployment to one selected cloud.
- Maintainability: modular monolith boundaries and provider/infrastructure adapters.

## Acceptance and evidence rules

Each Must requirement requires an automated test or an explicitly documented integration/manual verification step before release. A requirement is not considered implemented because an endpoint, dashboard, or configuration entry exists; the behavior must be observable and failure-tested. Metrics, screenshots, benchmark numbers, and deployment claims must originate from the running system and recorded evidence.

## Configuration policy

Limits, timeouts, retry counts, retention periods, provider selection, and resource settings are configuration defaults, not production guarantees. They must be observable and documented per environment.
