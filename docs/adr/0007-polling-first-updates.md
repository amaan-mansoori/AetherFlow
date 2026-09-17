# ADR-0007: Polling First

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

The initial frontend polls versioned API endpoints for job updates. SSE may be evaluated later based on measured load and UX need.

## Rationale

Polling is simpler to operate, test, secure, and deploy across the initial architecture.

## Consequences

The UI displays freshness and degraded states. Poll intervals and conditional requests must avoid unnecessary load.

