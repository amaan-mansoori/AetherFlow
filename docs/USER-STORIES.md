# User Stories

**Status:** Architecture / Specification Phase

## Developer user

- As a user, I can register and authenticate securely.
- As a user, I can create and revoke API keys without exposing previously stored secrets.
- As a user, I can submit a structured AI job and receive its identifier immediately.
- As a user, I can safely retry an identical request using an idempotency key.
- As a user, I can list and filter only my jobs.
- As a user, I can inspect job state, attempts, errors, timing, and validated result.
- As a user, I can request cancellation and see whether cancellation was accepted or could not stop an active provider call.
- As a user, I receive an actionable response when a limit or authorization rule blocks an action.

## Administrator

- As an administrator, I can inspect system-wide jobs, workers, queues, audit events, metrics, logs, and traces.
- As an administrator, I can distinguish queued, running, retrying, failed, and dead-lettered work.
- As an administrator, I can investigate a job using its request and trace correlation identifiers.

## Operator

- As an operator, I can run the system locally with deterministic mock inference.
- As an operator, I can deploy the same containerized processes to Kubernetes.
- As an operator, I can determine whether a failure is caused by the API, database, broker, Redis, worker, or provider.

