# API Error Contract

**Status:** Architecture / Specification Phase

Errors use a stable envelope:

```json
{
  "error": {
    "code": "IDEMPOTENCY_KEY_REUSED",
    "message": "The idempotency key was used with a different request.",
    "request_id": "req_...",
    "details": {}
  }
}
```

## Codes

| Code | HTTP | Meaning |
|---|---:|---|
| `VALIDATION_ERROR` | 400 | Request schema or semantic validation failed |
| `AUTHENTICATION_REQUIRED` | 401 | Credentials absent or invalid |
| `FORBIDDEN` | 403 | Principal lacks permission |
| `NOT_FOUND` | 404 | Resource is not visible or does not exist |
| `CONFLICT` | 409 | State or uniqueness conflict |
| `IDEMPOTENCY_KEY_REUSED` | 409 | Same key has a different fingerprint |
| `INVALID_STATE_TRANSITION` | 409 | Requested action is not valid for current state |
| `RATE_LIMITED` | 429 | Configured limit exceeded |
| `DEPENDENCY_UNAVAILABLE` | 503 | Required dependency unavailable |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

Identity endpoints additionally use `AUTHENTICATION_REQUIRED` for invalid/missing credentials and `FORBIDDEN` for authenticated users lacking a required role. Registration duplicate email is `CONFLICT`; invalid email/password request data is `VALIDATION_ERROR`. Authentication messages intentionally do not distinguish nonexistent accounts from incorrect passwords.

Responses include `request_id`; rate-limited responses include `Retry-After` and configured limit headers where safe. Internal stack traces, provider secrets, prompts, and raw credentials are never returned.
