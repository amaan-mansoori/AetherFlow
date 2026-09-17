# ADR-0005: At-Least-Once Processing

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

Design for at-least-once Kafka delivery and possible duplicate execution. Do not claim exactly-once execution.

## Rationale

At-least-once improves recovery when workers crash or acknowledgements are lost and avoids an unrealistic guarantee across an external provider.

## Consequences

CAS state claims, unique attempt/result constraints, and idempotent domain handling are mandatory. Provider-side duplicate work remains a limitation.

