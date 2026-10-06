# ADR-0024: Public Registration and Restricted Recruiter Demo

**Status:** Accepted  
**Date:** 2026-10-04

## Context

AetherFlow needs self-service user registration and a recruiter-facing demo
without replacing its existing identity model or weakening the established
server-side authorization boundary. The application already has a single
`users` table, normalized email registration, Argon2 password hashing,
short-lived bearer access tokens, rotating opaque refresh sessions, and
database-backed USER/ADMIN roles.

## Decision

- Reuse `POST /api/v1/auth/register`; do not create a second user table or
  authentication mechanism. Registration remains signed out and always assigns
  USER. Unknown fields are rejected, so role/owner/permission injection cannot
  grant privileges.
- Keep role assignment in a trusted operator path. The admin provisioning
  command promotes only an existing active non-demo account and records an
  audit event.
- Add only the DEMO role through migration `0007_demo_role`. Provision the
  reserved demo identity only when explicitly enabled and invoked by the
  trusted command. Its initial password comes from the operator environment,
  is Argon2-hashed, is not reset on reruns, and is never returned by an API.
- Treat DEMO as read-only at the API boundary: allow only the account's own
  read paths; reject submission, cancellation, API-key creation/revocation,
  and administrative actions. Add clearly labelled future-scheduled and
  cancellation-requested fixtures through existing domain services and stable
  idempotency keys. They remain undispatched and make no execution claim.
- Retain the refresh-cookie/session architecture. Newly issued access tokens
  carry their refresh-session family identifier; protected bearer requests
  verify a live family, so logout invalidates new tokens from that family.
  Tokens minted before this rollout remain compatible until their normal
  short expiration.
- Verify supplied browser Origins for login, refresh, and logout against the
  configured exact CORS allowlist. Continue to allow non-browser clients that
  omit Origin; protected API calls use explicit bearer credentials.
- Do not invent email verification or password reset flows. Registration
  creates an active USER account, but does not verify mailbox control.

## Consequences

The browser registration and demo pages reuse the existing auth client and
contracts. Session state remains in memory and is restored through the
HttpOnly refresh cookie. The demo is informative and safe to browse without
triggering provider execution or costs.

Operators must protect the demo password and the provisioning environment.
The public demo-availability route reports only whether the opt-in account is
available and its read-only mode. Redis-backed rate limiting remains optional
outside Compose and intentionally fails open during Redis outages. Production
deployment still requires HTTPS, secure cookie configuration, trusted secret
management, and an operator-controlled administrator provisioning process.
