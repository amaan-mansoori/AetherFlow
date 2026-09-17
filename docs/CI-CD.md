# CI/CD

**Status:** Architecture / Specification Phase

## Pull requests

Run formatting, linting, type checks, unit tests, integration tests where feasible, frontend checks, migration validation, build validation, and dependency/security checks. Use deterministic mock inference and disposable service dependencies.

## Main branch

Repeat validation, build immutable API/worker/frontend images, publish artifacts to a controlled registry, optionally deploy staging, and run smoke tests. Production promotion requires an explicit approval or equivalent controlled gate.

## Pipeline principles

Secrets are injected by CI configuration, never committed. Jobs are reproducible and fail closed on required checks. Artifacts identify source revision. Deployment rollback and migration compatibility are tested/documented before production use.

