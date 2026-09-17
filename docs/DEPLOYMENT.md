# Deployment Strategy

**Status:** Architecture / Specification Phase

## Local

Docker Compose must run frontend, API, worker/scheduler capability, PostgreSQL, Redis, Kafka, and optional observability profiles. A mock provider makes the core workflow credential-free. Environment variables are supplied through an ignored local file and documented example values only.

During Phase 1, Docker Compose is intentionally not added. The backend runs directly from a Python 3.12+ virtual environment against a configured PostgreSQL instance. Compose remains a later phase deliverable.

## Production decision

The cloud provider is an explicit open decision. Before implementation, select one provider using these criteria: managed PostgreSQL/Kafka/Redis availability, Kubernetes support, low portfolio-project cost, secret management, observability integration, and regional availability. Do not maintain simultaneous AWS/GCP/Azure designs.

## Kubernetes requirements

Provide reproducible manifests for API and worker Deployments, Services, configuration references, secret references, liveness/readiness probes, resource requests/limits, controlled migrations, and justified horizontal scaling. Kafka, Redis, and PostgreSQL should be managed services unless a documented operational reason requires self-hosting.

## Operations

Document image versioning, rollout, smoke checks, rollback, migration compatibility, backup/restore assumptions, and incident response. No production deployment claim is valid until executed from documented instructions.
