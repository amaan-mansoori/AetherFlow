# ADR-0022: Administrative Operations Control Plane

**Status:** Accepted
**Date:** 2026-10-02

## Decision

Add a small `ADMIN`-only API over durable job, attempt, lifecycle-event, and
transactional-outbox records. Use the existing centralized `require_admin`
policy, strict typed filters, bounded offset pagination, and deterministic
`created_at DESC, id DESC` ordering.

Admin detail responses omit job input and configuration, bound child
collections, and redact sensitive-looking operational values. Admin
cancellation calls the existing `cancel_job` service and versioned CAS state
machine. The successful mutation and safe audit record are committed together.

Do not add manual retry/requeue. The current state machine has no safe
administrator-initiated retry transition, and creating one without a complete
durable policy would bypass execution retry semantics or create duplicate
outbox work.

## Consequences

Operators can inspect real durable dispatch state and safely request
cancellation without a second control plane. Normal users retain ownership
boundaries, and no administrative route publishes to Kafka or uses Redis as
authority. SQLite tests cover authorization, redaction, bounded inspection,
CAS cancellation, and audit metadata; live PostgreSQL locking and Kafka
behavior remain infrastructure verification concerns.
