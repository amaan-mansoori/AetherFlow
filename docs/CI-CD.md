# CI/CD

**Status:** A pull-request/push quality workflow is implemented; artifact
publishing and deployment remain specification only.

`.github/workflows/ci.yml` runs backend tests, Ruff formatting/lint, mypy,
frontend tests, ESLint, TypeScript, production build, and Compose configuration
validation on pull requests and pushes to `master`. It does not start external
services, publish images, deploy, or perform production integration tests.

The workflow file is checked in, but its GitHub-hosted execution has not yet
been observed for the current uncommitted changes. Local command results are
recorded in [TESTING.md](TESTING.md).

## Pull requests

Run formatting, linting, type checks, unit tests, integration tests where feasible, frontend checks, migration validation, build validation, and dependency/security checks. Use deterministic mock inference and disposable service dependencies.

## Main branch

Repeat validation, build immutable API/worker/frontend images, publish artifacts to a controlled registry, optionally deploy staging, and run smoke tests. Production promotion requires an explicit approval or equivalent controlled gate.

## Pipeline principles

Secrets are injected by CI configuration, never committed. Jobs are reproducible and fail closed on required checks. Artifacts identify source revision. Deployment rollback and migration compatibility are tested/documented before production use.
