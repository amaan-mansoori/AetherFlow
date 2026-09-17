# Threat Model

**Status:** Architecture / Specification Phase

| Threat | Control | Residual risk |
|---|---|---|
| Credential stuffing/password attack | Slow password hashing, rate limits, generic auth errors, future lockout policy | Requires operational detection |
| JWT theft | Short-lived tokens, TLS, secure storage decision, revocation strategy | Token valid until expiry |
| API-key leakage | Hash-only storage, one-time display, redacted logs, revoke endpoint | Client environment may leak secret |
| Object authorization bypass | Central policy checks and negative tests | New endpoints can regress |
| Duplicate work/replay | Idempotency records, state CAS, unique results, at-least-once design | External provider may run twice |
| Prompt/indirect injection | Treat input/output as data, no tools/shell, output schema validation | Model may produce harmful text |
| Resource exhaustion | Payload limits, rate limits, bounded timeout/retries, quotas/configuration | Distributed abuse needs monitoring |
| SQL injection | ORM/parameterized queries, validation, security tests | Dependency vulnerabilities |
| XSS | Output escaping and safe rendering | Browser/platform defects |
| CSRF | Explicit token transport and CSRF policy | Depends on final auth transport |
| SSRF/command injection | No arbitrary URLs/tools/shell; allowlists if future integrations | Future feature expansion |
| Kafka/Redis/database outage | readiness, retries, backpressure, clear degraded behavior, runbooks | Availability depends on deployment |
| Secret/container compromise | Secret manager, non-root images, scanning, least privilege | Cloud/operator compromise |

Security testing must include authorization matrices, malformed payloads, credential handling, output rendering, dependency scanning, and failure/degraded-mode behavior.

