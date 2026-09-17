# ADR-0004: Redis Is Ephemeral

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

Use Redis for rate limits, short-lived caches, and only narrowly justified coordination. Never use it as job/result/audit authority.

## Rationale

These workloads benefit from low-latency expiry semantics without compromising durable state.

## Consequences

Every Redis feature defines key format, TTL, invalidation, and unavailable behavior. Cached data may be stale within its documented TTL.

