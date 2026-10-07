# Deployment

**Status:** Local Docker Compose implemented; cloud and Kubernetes deployment
are not implemented or verified.

## Local development

`docker-compose.yml` starts PostgreSQL, Kafka, Redis, the one-shot Alembic
migration process, the FastAPI API, worker, outbox publisher, and scheduler.
The Next.js frontend runs separately with Node.js. The deterministic mock
provider is the default, so the local job-processing path does not require an
external AI credential.

Follow the copy-safe configuration and startup steps in the
[README quick start](../README.md#quick-start). The local `.env` file is
untracked development configuration, not a production secrets solution.

## Production status

There is no selected cloud provider, live deployment, Kubernetes manifest set,
Helm chart, or production deployment verification. The desired deployment
topology and rollout criteria below are proposals, not delivered artifacts.

Before a production target is selected, evaluate cost, managed PostgreSQL and
Kafka availability, secret management, regional requirements, and operational
ownership. A production plan must define TLS termination, secret injection,
resource requests/limits, migration ordering and compatibility, health probes,
backups and restoration, broker/database availability, rollout/rollback, and
incident response. Any provider-specific design should be recorded in an ADR;
do not treat this document as evidence that those controls exist.
