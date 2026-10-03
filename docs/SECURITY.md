# Security Requirements

**Status:** Architecture / Specification Phase

## Principles

Least privilege, deny by default, explicit authorization, defense in depth, secure defaults, auditable mutations, and fail closed for authentication/authorization decisions.

## Identity and secrets

Passwords use a current memory-hard password hashing configuration. JWT signing keys, database credentials, broker credentials, Redis credentials, and provider keys come from environment-specific secret management, never source control. API keys are shown once and stored only as a secure hash plus non-secret metadata.

Phase 2 uses Argon2id through `argon2-cffi` for passwords. Access JWTs are signed with an environment-provided secret and expire after a configurable short lifetime (15 minutes by default). Refresh credentials are random opaque values, stored as SHA-256 hashes, rotated on use, and revoked on logout or reuse detection. Browser refresh credentials are `HttpOnly`, `SameSite=Strict`, path-scoped cookies; `Secure` is required in production. Bearer access tokens remain appropriate for API clients.

## Input and output

Validate sizes, types, models, timeouts, priorities, metadata, and structured output schemas. Use parameterized database operations. AI output is untrusted data: it is escaped for UI display and never interpreted as HTML, SQL, shell, URL, or executable code. The AI system cannot execute arbitrary shell commands.

## Web/API controls

Enforce authentication and object-level authorization on every protected resource. Define CORS narrowly. Choose cookie or header transport deliberately and apply CSRF protection when browser credentials are automatically attached. Apply rate limits and request size limits before expensive processing.

Phase 2 separates authentication dependencies from authorization policies. `USER` is assigned during registration; `ADMIN` is database-backed and cannot be self-assigned. A request cannot provide both bearer and API-key credentials. Cookie-based refresh endpoints are same-site and path-scoped; a future cross-site browser deployment must add an explicit CSRF token/origin policy rather than weakening cookie settings.

Identity request schemas reject unknown fields, including attempted client-controlled role fields, and reject blank API-key names. CORS is allowlist-based and explicitly permits only the implemented methods and authentication headers.

## Logging

Redact authorization headers, API keys, passwords, provider credentials, raw prompts/outputs when sensitive, and personal data according to configuration. Log stable identifiers, classifications, and hashes/fingerprints rather than secrets. Audit security-sensitive actions.

Security audit events cover registration, successful/failed login, refresh creation/rotation/reuse failure, logout, API-key creation/revocation, and authorization denial. Audit context contains only safe metadata such as public key ID and reason.

Phase 13 administrative routes use the centralized `require_admin`
dependency; authentication is still required and normal `USER` principals
receive `403`. Admin job responses omit raw input/configuration, bound child
collections, and redact sensitive-looking keys and operational error strings.
Administrative cancellation records the server-derived actor, target,
operation, result, and request ID in the existing audit log. No admin
operation accepts client actor identity or publishes directly to Kafka.

The unauthenticated `/metrics` endpoint exposes only bounded operational
labels and counters. It does not expose job IDs, request IDs, user data,
paths with identifiers, credentials, authorization headers, or exception text.

The application image runs as a non-root user and excludes `.env` and `.git`
through `.dockerignore`. Compose secrets are injected through environment
substitution for local development; production deployments must use external
secret management and must not reuse the example credentials.

## Provider configuration

Provider selection uses a non-secret identifier from job configuration or the
runtime `provider_default` setting. Provider credentials are supplied only
through deployment environment/secret management; job schemas reject
credential-like keys, including nested configuration values, and provider
adapters never receive database sessions or persist credentials. The
deterministic mock provider requires no credentials. Provider errors and
identifiers may be persisted in attempts, but raw prompts, outputs, and
credentials are not logged by the provider boundary.

Phase 9 provider credentials are read only from
`AETHERFLOW_PROVIDER_OPENAI_API_KEY`. They are held by the worker-side HTTP
adapter and are never persisted in jobs, attempts, events, Kafka payloads,
metrics, API responses, or exception messages. Provider request and response
bodies are not logged.

Phase 10 review found no tracked `.env` file or provider secret in the
application configuration. Compose uses environment substitution and does not
contain a real credential. Infrastructure log validation is **UNVERIFIED**
because the Docker runtime could not be started.

Redis URLs are environment configuration and are never logged. Rate-limit keys
contain only a fixed namespace, class, and truncated digest of an opaque
identity. Raw API keys, JWTs, refresh tokens, provider credentials, and request
headers are not stored in Redis. Redis has no public Compose port.

## Supply chain and containers

Pin and review dependencies, scan dependencies and images in CI where practical, use minimal non-root images, read-only filesystems where feasible, drop Linux capabilities, and avoid privileged containers.
