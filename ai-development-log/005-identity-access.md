# AI Development Log 005: Identity and Access

**Date:** 2026-09-16  
**Phase:** Phase 2 - Identity and Access Foundation  
**Objective:** Add secure multi-user identity, access authentication, refresh sessions, roles, API keys, audit events, and migrations without implementing jobs or distributed runtime components.

## Important AI proposals

- Use Argon2id for password storage.
- Return short-lived JWT access tokens and store long-lived refresh credentials as hashed opaque values.
- Rotate refresh credentials on every use and revoke the session family on reuse detection.
- Use an indexed public API-key identifier plus a SHA-256 digest of a high-entropy secret for efficient lookup without storing the secret.
- Keep authentication dependencies separate from reusable authorization policies.
- Use an HttpOnly, SameSite=Strict, path-scoped refresh cookie and bearer access tokens for API requests.

## Accepted decisions

- Registration normalizes email, validates password length (12-128 characters), and always assigns `USER`.
- Access tokens default to 15 minutes; refresh sessions default to 30 days and are configurable.
- JWT claims contain only subject, roles, issued/expiry times, and token type.
- Refresh tokens are opaque, hashed at rest, rotated, and family-revoked on reuse.
- API keys use `afk_<public-id>_<secret>`, are shown once, and authenticate through `X-API-Key`.
- Supplying bearer and API-key credentials together is rejected.
- `USER` and `ADMIN` are seeded by migration; no public role-assignment endpoint exists.
- Security-sensitive actions write safe audit records without credentials.

## Rejected alternatives

- Plaintext or recoverable refresh/API-key storage.
- Indefinitely valid access JWTs.
- Returning refresh credentials in JSON.
- Client-controlled registration roles.
- Expensive Argon2 verification on every API-key request.
- Redis-backed identity state or rate limiting in this phase.
- Jobs, Kafka, Redis, providers, workers, frontend, Kubernetes, and telemetry infrastructure.

## Security considerations

Authentication failures use generic messages to resist account enumeration. Production settings require a sufficiently long JWT secret and secure cookies. Password hashes, tokens, API-key secrets, and credentials are excluded from response schemas and audit context. Refresh cookie CSRF posture is SameSite/path constrained; a future cross-site browser deployment must add an explicit CSRF/origin control.

## Implementation summary

Added identity SQLAlchemy models and migration, seeded roles, Argon2 password helpers, JWT/opaque-token operations, authentication and admin dependencies, registration/login/me/refresh/logout routes, API-key lifecycle routes, audit service, configuration fields, and security-focused tests. Phase 1 health and error behavior remains intact.

## Hardening review

The Phase 2 review added malformed Argon2 hash handling so corrupted credential records fail closed as authentication failures, strict request schemas that reject unknown security-sensitive fields, blank API-key name validation, complete CORS coverage for the implemented API-key and revocation routes, and failed refresh audit records for missing, expired, or inactive-user sessions. No new product capability was added.

## Tests executed

- Ruff format check and lint: passed.
- mypy: passed.
- `pytest backend/tests`: 27 passed.
- Alembic upgrade and downgrade on a clean isolated SQLite database: passed.

## Problems encountered and solutions

The initial refresh test exposed SQLite's naive datetime return values; refresh expiry comparison now normalizes database timestamps to UTC. FastAPI `204` response handling required logout to mutate the injected response and return `None`. Dependency linting was addressed with module-level dependency aliases. Migration commands now require the configured JWT secret, as runtime settings intentionally have no insecure secret fallback.

## Remaining limitations

No PostgreSQL server, external identity provider, Redis rate limiting, brute-force throttling, password reset, email verification, refresh-cookie CSRF token, or frontend integration is included. These are explicit future decisions or later-phase work. API-key last-used updates are best-effort durable metadata updates on authenticated requests.
