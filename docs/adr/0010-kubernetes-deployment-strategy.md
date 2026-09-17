# ADR-0010: Kubernetes Deployment Strategy

**Status:** Accepted with open provider selection  
**Date:** 2026-09-16

## Decision

Use reproducible plain Kubernetes manifests initially, with API and worker deployments, probes, resources, configuration, secrets, migrations, and justified horizontal scaling. Select one cloud provider before implementation deployment work. Defer Helm until repeated templating justifies it.

## Rationale

Plain manifests keep the first deployment understandable and avoid adding a packaging abstraction before environment variation exists.

## Consequences

The cloud target and managed versus self-hosted dependency choices remain explicit Phase 1 gates. No multi-cloud deployment claim is made.

