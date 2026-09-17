# ADR-0002: PostgreSQL Is Authoritative

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

PostgreSQL is authoritative for identity, job state, attempts, results, events, workers, audit records, and idempotency.

## Rationale

Durable queries, constraints, transactions, and operational inspection are more appropriate for current state than Kafka or Redis.

## Consequences

Database schema and migrations are critical deployment artifacts. Kafka and Redis failures must never be hidden as durable success.

