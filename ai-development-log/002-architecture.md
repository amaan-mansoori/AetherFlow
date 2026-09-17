# AI Development Log 002: Architecture

**Date:** 2026-09-16  
**Task:** Convert the approved architectural direction into an implementable architecture.

## AI proposal

Use a modular monolith with independently runnable FastAPI API and worker processes, an initially co-locatable scheduler, PostgreSQL authority, Kafka dispatch/events, Redis ephemeral capabilities, provider adapters, and an observability stack.

## Accepted decisions

Use at-least-once processing, explicit state transitions, application/domain idempotency, row/CAS concurrency protection, polling-first frontend updates, and Kubernetes manifests before Helm.

## Rejected alternatives

Premature microservices, Kafka as current-state storage, Redis as durable job storage, exactly-once claims, immediate WebSockets, and simultaneous multi-cloud deployment.

## Reasoning

The selected boundaries correspond to real runtime and reliability concerns while preserving local simplicity and testability.

## Changes

Created architecture, data-flow, database, reliability, scaling, tradeoff, deployment, and ADR documents.

## Open questions

Cloud target and managed dependency choices require a Phase 1 decision gate.

