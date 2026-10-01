# ADR-0006: AI Provider Abstraction

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

Business logic depends on an internal provider interface and normalized
request/response/error models. The deterministic mock provider implements the
interface first; external adapters must use the same boundary when introduced.

## Rationale

Vendor SDK behavior, credentials, errors, and schemas must not leak into domain logic. A mock enables deterministic local/CI behavior.

## Consequences

Provider adapters must normalize timeouts, rate limits, usage, and output validation. Provider-specific capabilities may not be universally portable.
