# Phase 9 — Real Provider Integration and Production Validation

## Implementation

Added an OpenAI-compatible chat-completions adapter behind the existing
provider registry. It uses a reusable bounded async `httpx` client, configured
timeout, allowlisted model request options, normalized text/usage output, and
safe failure classification. No adapter retry loop was added; Phase 6 remains
the retry authority.

Provider API keys are environment-only settings. The worker initializes and
closes the provider client; the API process does not. The mock provider remains
credential-free and the default.

## Verification

Deterministic tests use `httpx.MockTransport` and cover success, usage,
malformed output, authentication, rate limit, timeout, transient 5xx,
permanent 4xx, unsupported configuration, and secret non-leakage. Full
application tests, formatting, linting, typing, and migration checks are run
separately.

## Environment limitations

Real provider credentials were not used or recorded. Docker, PostgreSQL, and
Kafka availability must be checked before claiming end-to-end deployment or
real-provider validation. No external provider request is fabricated by the
test suite.
