# Phase 11 — Redis Coordination and Distributed Rate Limiting

## Implementation

Added an optional lifecycle-owned async Redis client with bounded pooled
connections, URL/configurable timeouts, ping, and clean shutdown. Added an API
middleware using atomic Lua fixed-window increments for two classes:
`auth` (20 requests/60 seconds) and `api` (120 requests/60 seconds). The
default is disabled; Compose enables Redis for the API only.

Rate-limit keys use a fixed namespace and truncated digest of a stable opaque
identity. API-key public IDs may identify a caller, but secrets, JWTs, refresh
tokens, provider credentials, and raw headers are never written to Redis.

## Failure semantics

Rate limiting is fail-open. Redis outages bypass only rate-limit enforcement,
record bounded operational metrics, and do not affect authentication,
PostgreSQL durability, the transactional outbox, Kafka, workers, or retries.

## Verification

Four deterministic tests pass using an injected fake async Redis boundary:
atomic decision shape/TTL inputs, 429 and `Retry-After`, class/key separation,
and Redis timeout fail-open behavior. Compose configuration validates with the
internal Redis service. Real Redis startup, TTL expiry against a server, and
multi-process sharing remain unverified when Docker is unavailable.
