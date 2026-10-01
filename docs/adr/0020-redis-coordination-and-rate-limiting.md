# ADR-0020: Redis Coordination and Distributed Rate Limiting

## Status

Accepted — Phase 11.

## Decision

AetherFlow adds an optional, API-owned async Redis client with bounded
connection pooling and timeouts. Redis is used only for ephemeral
coordination:

```text
PostgreSQL = durable source of truth
Kafka      = asynchronous transport
Redis      = ephemeral coordination/rate limiting
```

The API applies two fixed-window classes: `auth` for `/api/v1/auth/*` and
`api` for other `/api/v1/*` routes. The default limits are 20 and 120 requests
per 60 seconds. One Lua script atomically increments a namespaced key and sets
its TTL on first use. Keys contain a class and truncated digest, never raw
credentials or headers. Responses expose bounded limit/remaining headers and
return 429 with `Retry-After` after the limit.

Redis is explicitly disabled by default outside Compose. When enabled but
unavailable, rate limiting fails open because it is non-critical coordination.
The middleware emits bounded metrics and a non-per-request warning. Authentication,
job state, idempotency, retry scheduling, outbox correctness, and worker
execution remain PostgreSQL/Kafka responsibilities and never depend on Redis.

## Consequences

Multiple API instances can share the same Redis window, subject to normal
Redis availability and fixed-window boundary behavior. A Redis outage permits
traffic rather than corrupting or blocking durable operations. Redis is not an
exactly-once mechanism, lock service, job store, or retry store.
