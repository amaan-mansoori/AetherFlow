# Phase 14 — Production Operations Frontend

## Implementation

Added a Next.js/TypeScript operations console with a shared dark visual system,
responsive application shell, role-aware navigation, keyboard command palette,
login/session handling, job overview/list/activity, structured job submission,
execution detail, and ADMIN operations.

The API client is centralized, typed, abortable, and maps the backend error
envelope and `Retry-After`. Access tokens stay in memory; session restoration
and rotation use the backend's HttpOnly refresh cookie. The console makes no
worker health, global count, global activity feed, retry action, or admin
result-body claim unsupported by the backend.

The job detail frontend requests bounded history pages. Optional `limit` and
`offset` parameters were added to the existing per-job events and attempts
routes, preserving the existing full-history response when omitted.

## Verification status

Frontend behavior is covered with Vitest/Testing Library for API error parsing,
session refresh, page parameters, submission validation, status labels, command
palette keyboard behavior, admin access, and cancellation confirmation.
Production typecheck, lint, and build are executed for this phase. Backend
regression and SQLite migration lifecycle are rerun. Live infrastructure
verification is reported only if the Docker runtime is available.

## Browser and responsive verification

Exercised login, overview, submission, list/detail, ADMIN inspection and
backend-authoritative cancellation, plus command-palette search/navigation,
Escape handling, and the mobile navigation drawer against a disposable
SQLite-backed FastAPI process. Kafka, Redis, and the scheduler were disabled;
the deterministic mock provider was used. The test job remained in the
backend-observed `CANCEL_REQUESTED` state, with no worker execution claimed.
Reviewed desktop screenshots for overview, admin, and execution detail and
mobile screenshots for jobs, activity, submission, admin, and execution
detail. Responsive checks covered 375, 390, 768, 1024, 1280, and 1440 CSS-pixel
viewports. The mobile overview table's intrinsic minimum-width overflow was
corrected and rechecked. This does not verify Compose/PostgreSQL/Kafka/Redis
integration or replace a maintained browser E2E suite.
