# ADR-0023: Production Operations Frontend

**Status:** Accepted  
**Date:** 2026-10-04

## Decision

Build the production operations console as a Next.js App Router application
with TypeScript, React, CSS-variable design tokens, and Lucide icons. Keep one
typed API client responsible for bearer headers, cookie credentials, refresh,
error mapping, and abortable requests. Do not add a server-side proxy or store
access tokens in browser persistent storage.

The API remains authoritative for identity, object permissions, job state,
retry policy, schedule activation, cancellation, and admin operations. The
browser requests only supported API capabilities. Detail history uses
optional `limit`/`offset` parameters on user event/attempt endpoints to avoid
unbounded console history requests; omitting the parameters retains the
previous API response behavior.

Use short CSS micro-interactions and `prefers-reduced-motion`; avoid a separate
animation framework. Display only values derived from bounded API responses.
Because the API has no aggregate job-count endpoint, overview values are
explicitly labeled as a recent visible-job sample.

## Rationale

The console requires client-side authenticated interaction and an operational
shell, but has no need to duplicate domain rules or introduce a data-fetching
or animation framework. An in-memory bearer token and the backend's HttpOnly
refresh-cookie flow preserve the established browser credential design.
Direct API calls keep the trust boundary clear: UI role checks are convenience
only, and FastAPI's `require_admin` remains mandatory.

## Consequences

The interface can submit, inspect, cancel, and administer jobs through real
API contracts with bounded list/history requests. The design includes explicit
limitations: there are no account-wide counts, global activity feed, worker
registry, admin result body, or real-time event stream. Live PostgreSQL/Kafka/
Redis integration remains a separate infrastructure verification.
