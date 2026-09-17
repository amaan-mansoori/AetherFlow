# ADR-0003: Kafka for Job Dispatch

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

Use `jobs.submit` for durable dispatch and `jobs.lifecycle` for lifecycle distribution. Workers use a consumer group; PostgreSQL remains state authority.

## Rationale

Kafka provides durable asynchronous decoupling, consumer scaling, and replayable operational events relevant to this product.

## Consequences

Messages are versioned, partitioned by job ID for per-job ordering, retained according to environment policy, and processed at least once. Kafka operations are explicitly documented and tested.

