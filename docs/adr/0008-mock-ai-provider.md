# ADR-0008: Mock AI Provider

**Status:** Accepted  
**Date:** 2026-09-16

## Decision

Provide a deterministic mock provider for local development, tests, CI, and benchmarks. It is explicitly labeled as non-production inference.

## Rationale

Tests must not depend on credentials, provider availability, cost, or nondeterministic model output.

## Consequences

Mock latency/errors are controlled test fixtures and cannot support claims about external model quality or production provider performance.

