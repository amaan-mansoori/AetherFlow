# Production Operations Console

## Design audit and implementation plan

The current console shares one bordered-panel treatment across unrelated
screens, repeats small uppercase monospace labels for navigation and content,
and gives every overview metric identical visual weight. Its “Failed” summary
also combines `FAILED` and `DEAD_LETTERED` records, so the label overstates
what that count means. The mobile login places the product story ahead of the
form even though signing in is its only task.

Reference access was limited. The Trickle landing page rendered in the browser,
but offered no relevant operations-console components. Linear’s fetched page
contained activity text rather than usable design examples; Vercel and 21st.dev
pages/previews failed to load, and CollectUI returned only its subscription
landing text. The actual shadcn source for sidebar, command, dialog, button,
input, table, and field patterns was reviewed. Existing AetherFlow components
were restyled using compatible accessibility and interaction patterns; no
third-party component source was transplanted and no 21st.dev component was
adopted without an accessible preview.

Implementation plan:

1. Load Inter Variable and IBM Plex Mono from local package assets, retaining
   system fallbacks for offline or failed font loading.
2. Rework shared tokens and typography; reserve filled surfaces for focused
   controls and layered UI, using alignment and dividers for operational
   sections instead of repeating panels.
3. Recompose login for quick mobile access, make overview state counts exact
   and actionable, and refine job, activity, admin, submission, and execution
   layouts without changing their API or authorization behavior.
4. Preserve accessible navigation, command, and confirmation interactions;
   validate real routes at the requested viewport sizes and run frontend
   checks.

## Architecture and API boundary

The console is a Next.js App Router application written in TypeScript. It calls
the FastAPI service at `NEXT_PUBLIC_API_BASE_URL` through one typed client in
`frontend/lib/api/client.ts`; no business state is simulated in the browser.
Job state, permission, retry decisions, schedule activation, and cancellation
remain backend responsibilities.

The client consumes:

- `POST /api/v1/auth/register`, `GET /api/v1/auth/demo`,
  `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`,
  `POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`
- `GET/POST /api/v1/jobs`, job detail, per-job events and attempts, and the
  existing cancel route
- Phase 13 `GET /api/v1/admin/jobs`, admin detail, and audited admin cancel
- `GET /health/live` and `GET /health/ready`

Registration creates a standard USER account and leaves it signed out. No email
verification or password-recovery service is configured. The recruiter DEMO
identity is available only after explicit operator provisioning; it is
labelled read-only in the console and the API independently denies writes and
administrative access. Use `AETHERFLOW_DEMO_PASSWORD` only in the trusted
provisioning environment, never as a `NEXT_PUBLIC_` setting.

No API key creation or one-time key secret is exposed through this console.
Admin list/detail/cancel calls are still protected by FastAPI's `require_admin`
policy; client role checks only shape navigation and provide early UX.

## Authentication and errors

Login returns a bearer access token and sets the backend's HttpOnly refresh
cookie. The access token is held only in JavaScript memory (not local storage,
session storage, a URL, or logs). Fetch requests use `credentials: include` so
refresh/logout preserve the cookie contract. On page load, a refresh request
restores a session. An authenticated `401` causes a single refresh attempt and
one retry; an invalid refresh clears the local session. Cross-origin
development requires the API CORS origin to allow credentials for the console.
The refresh cookie is `SameSite=Strict`, so local development should use the
same hostname on both sides (`localhost:3000` and `localhost:8000`); mixing
`localhost` with `127.0.0.1` makes them different sites and can prevent session
restoration.

The shared API error parser reads the documented `{error: {code, message,
request_id, details}}` envelope and `Retry-After`, gives safe contextual
messages for common errors, and never displays stack traces. Request IDs are
shown only where safe. Calls accept `AbortSignal`; polling requests are aborted
when a detail route unmounts or changes.

## Pages and interaction

- **Overview:** health/readiness from the API and counts/distribution computed
  only from the most recent 100 jobs visible to the signed-in user. These are
  explicitly labeled a sample, not totals or global KPIs.
- **Jobs:** 20-row bounded pages, server-side state filter, and text/schedule
  filters over the currently fetched page. The existing list API does not
  expose a total count or search parameters.
- **Submit:** actual `structured_inference` payload (`input.prompt`), model,
  configuration/metadata JSON objects, priority, timeout, retry policy,
  optional local datetime normalized to ISO UTC, and a generated
  `Idempotency-Key`. Provider credentials are never accepted or rendered.
- **Execution detail:** actual job detail plus bounded event/attempt pages;
  ADMIN detail uses the redacted Phase 13 response, including bounded durable
  outbox dispatch records. Timeline entries show persisted event names and
  states, not invented dispatch states. Result data is shown only when the
  authenticated job detail API returns it; admin responses intentionally omit
  result bodies.
- **Activity:** the latest 50 visible job records sorted by actual `updated_at`.
  It is not a global lifecycle event feed.
- **Admin:** bounded typed job filters, offset pages, detail, dispatch
  visibility, and cancellation through the existing CAS-backed API.

Execution detail centralizes polling in one component at a 10-second interval,
pauses while the tab is hidden, avoids overlapping requests, aborts stale
responses, and stops after an observed terminal state. There is no WebSocket
or worker/service registry in the backend contract.

## Visual system and accessibility

The console uses a near-black canvas, flat charcoal surfaces, restrained
mint/sage accents, and semantic state colors. Inter Variable is self-hosted
from Fontsource for UI text; IBM Plex Mono is self-hosted for identifiers,
timestamps, and structured output, with system fallbacks for offline use.
Typography, color, spacing, radii, focus, and responsive layout tokens live in
`frontend/app/product.css`. Lucide is the single icon family. Motion is limited
to short navigation, dialog, loading, and observed running-state feedback;
reduced-motion preferences are respected.

Overview summaries use a divided metric strip rather than independent cards.
Job tables retain aligned columns on desktop and use compact, content-aware
rows with labelled timestamps on mobile. Login uses a product-specific two-column composition on wide
screens and a stacked form on mobile. Panels are reserved for related
operational groups instead of wrapping every element in a card.

The responsive shell collapses its sidebar at intermediate widths and becomes
a touch-friendly drawer on mobile. Job tables become compact cards on narrow
screens. Buttons, forms, status labels, error announcements, modal focus
handling, keyboard command navigation (`Ctrl/Cmd+K`, arrows, Enter, Escape),
and visible focus states are implemented with semantic elements and labels.
The sidebar, command, dialog, button, input, table, and field patterns were
compared against accessible shadcn source. These references informed interaction
choices; no third-party component source was transplanted.

## Visual QA scope

After the final production build, the authenticated overview, jobs, submit,
activity, admin, and detail routes were opened in the browser at all six
requested viewports: 1440x900, 1280x800, 1024x768, 768x1024, 390x844, and
375x812 (36 route/viewport checks). No document-level horizontal overflow was
found. The 768px admin table remains intentionally horizontally scrollable
inside its table viewport; its parent no longer expands the page. Screenshots
were visually reviewed for overview at 1440x900, admin at 768x1024, and job
detail at 390x844. Earlier in this redesign pass, login was reviewed at
1440x900 and 390x844, the jobs list at 375x812, and submit, activity, admin,
and the mobile navigation drawer were inspected in the browser. Both font
families were confirmed in computed browser styles.

Browser checks against a disposable SQLite-migrated FastAPI instance covered
real user/admin sign-in, role-restricted admin access, immediate and scheduled
job submission, list/detail/activity/admin views, API-backed model/state
filters, ID-copy confirmation, mobile drawer open/close and route navigation,
and cancel confirmation with the server's `CANCEL_REQUESTED` response.
Reduced-motion preferences were confirmed to shorten transitions and
animations. Browser route changes abort in-flight prefetches as expected. The
app retained live API integration throughout; QA records were not added as UI
fixtures.

This review did not run Kafka, Redis, the scheduler, workers, provider
execution, PostgreSQL, or Docker Compose integration. No worker execution
result, cross-service health, or production database behavior is claimed.
Linear's fetched content did not provide usable design examples; Vercel and
21st.dev pages/previews were inaccessible; CollectUI exposed only subscription
content; and Trickle rendered a marketing page rather than an operations
component reference. No screenshots or animations from inaccessible sources
are claimed as inspected.

## Development and validation

From `frontend`, copy `.env.example` to `.env.local`, install with `npm
install`, and run `npm run dev`. Available quality commands are `npm run
lint`, `npm run typecheck`, `npm test`, and `npm run build`. Frontend component
tests use Vitest and Testing Library. `backend/tests/test_phase14_api_pagination.py`
protects the optional bounded user-history query contract; omitted pagination
parameters retain the previous full-history response behavior.

SQLite/unit verification does not establish live PostgreSQL locks, Kafka
delivery, Redis coordination, or end-to-end Compose behavior. Such runtime
claims require a working Docker Linux engine and are not inferred from console
health checks.
