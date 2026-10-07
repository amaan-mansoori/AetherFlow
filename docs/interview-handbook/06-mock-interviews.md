# Chapter 21 — Mock Interviews

## Recruiter introduction (30 seconds)

> AetherFlow is a local-first distributed AI job orchestration project. It
> accepts authenticated, idempotent job submissions, persists job state and
> dispatch intent together, publishes through an outbox to Kafka, and runs
> work in leased workers through a provider abstraction. I focus on being
> precise about its guarantees: delivery is at least once, provider execution
> can repeat, and the project has local tests but no verified public
> production deployment.

Personalize the contribution sentence only with work you actually performed.

## Project walkthrough (2 minutes)

> A synchronous inference endpoint couples user latency and availability to
> the provider. AetherFlow returns a durable job ID instead. The FastAPI
> submission path validates a Pydantic request, authenticates the user,
> scopes an idempotency key, and stores the job and outbox intent in one
> PostgreSQL transaction. Future jobs remain accepted until their UTC due
> time.
>
> A separate publisher leases an outbox row, publishes a versioned dispatch
> to Kafka, then records publication. A crash after Kafka accepts but before
> that final update can duplicate a message. The worker disables Kafka
> auto-commit, checks job state and version, records a `RUNNING` lease and
> attempt, and calls a provider adapter outside the database transaction.
> Result/failure state is persisted; selected transient failure types receive
> bounded retries with durable future dispatch intent.
>
> A scheduler activates one-shot due jobs in PostgreSQL. The Next.js console
> reads job, event and attempt data and polls while the detail page is active.
> Redis is an optional fail-open API rate limiter, not a queue or job cache.
> The mock provider makes local execution repeatable. Current verification is
> strong on deterministic unit/API/UI paths and limited local Compose smoke,
> but does not establish PostgreSQL lock races, Kafka rebalances or production
> operation.

## Architecture explanation (5 minutes)

Use Chapter 1's seven-step walkthrough and draw the Chapter 3 component
diagram. Speak in invariants, not a list of products:

1. PostgreSQL owns job state.
2. Submission and immediate dispatch intent share one DB transaction.
3. Kafka delivers a notification at least once.
4. Worker state/version checks protect durable transitions, not provider
   side effects.
5. Retryable failure and retry intent commit together.
6. A result is the evidence stale-lease recovery uses to reconcile completion.
7. API readiness is not end-to-end dispatch readiness.

If asked to claim a stronger guarantee, name the missing boundary and what
evidence would be required.

## Senior engineer deep-dive scenario

**Interviewer:** “The LLM returns success. The worker process dies before the
job is shown as complete. What happens?”

**Model reasoning:** First distinguish whether the result row committed. If
the result is durable but the terminal job transition did not, stale-lease
recovery can observe the result and reconcile to `SUCCEEDED`. If no result is
durable, the system cannot know whether the provider performed work. The
lease eventually expires and the current recovery path records failure;
subsequent retry/re-delivery could repeat work depending on the path and
policy. I would inspect attempt timestamps, result row, state version, lease
and logs before concluding which window occurred.

**Follow-up:** “How would you improve this?” Make the local result/attempt/
terminal-state persistence atomic where feasible; add a provider idempotency
key when supported; inject crashes at both sides of the commit; validate
PostgreSQL races. Do not promise an atomic commit with an external provider.

## Distributed-systems failure debugging scenario

**Interviewer:** “New jobs stay `ACCEPTED`; API and database look healthy.”

**Model reasoning:**

1. Determine whether the job has a future `schedule_at`. A future accepted
   job may be waiting as designed.
2. For immediate work, inspect the matching outbox row, available time,
   publication state, lease and attempt/error metadata.
3. Check publisher process logs/configuration and broker advertised listener
   from the publisher container network.
4. If the outbox says published, inspect Kafka topic/group lag, partition
   assignment, worker process and deserialization errors.
5. Compare message job version with current DB state. A stale/terminal no-op
   is not a stuck job.
6. Correlate request/job IDs and metric counters; metrics may reset at process
   restart. Do not rerun a job or delete a volume to make the symptom disappear.

This sequence follows evidence across durable boundaries rather than assuming
the API's readiness probe covers Kafka or a worker.

## Code-review scenario

**Proposed change:** publish to Kafka directly inside `submit_job` and delete
the outbox for simplicity.

**Model review:** The proposed code creates a dual-write gap: if the database
commits and Kafka publish fails, the job remains accepted without durable
dispatch intent; if publish occurs first and DB commit fails, the worker can
see a nonexistent job. Publishing inside a DB transaction does not make Kafka
part of the transaction and lengthens lock/connection duration. Preserve the
outbox unless requirements and failure policy intentionally change. Add a
test for commit-before-publish crash and duplicate publication after broker
acknowledgement.

## Skeptical interviewer challenge round

**“Is this exactly once?”** No. Dispatch is at least once; provider effects
can repeat.

**“Then why use a lease?”** It bounds ownership and helps recover stale
durable state; it cannot fence a remote provider without provider cooperation.

**“Why not skip Kafka?”** A DB queue may be simpler; the current design values
a separate partitioned dispatch stream, at the cost of broker operations.

**“Is the demo production-safe?”** It is read-only and opt-in, but a public
deployment still needs abuse controls, secrets, TLS, quotas, monitoring and
tested infrastructure recovery.

**“Why no public demo?”** State the true reason. The repository verifies local
workflows, not a public deployment. Cost and secrets are considerations, not
known personal history.

**“What is weakest?”** Cite a verifiable gap such as missing PostgreSQL lock
race/Kafka rebalance testing or deterministic retries without applied jitter.
Then state a concrete next test/change.

**“What would you build next?”** Prioritize the failure-injection integration
tests and durable operational observability before adding a new broker or
microservice.

## Answering follow-ups without scripts

- Clarify the failure boundary the question targets.
- State what the database, broker, and provider each know at that point.
- Walk the timeline and identify durable evidence.
- Separate current implementation from proposed improvement.
- Say what test or source file would verify the answer.
- If uncertain, say what is unknown and how you would measure/inspect it.

# Chapter 22 — Source-Code Navigation Guide

Paths below are repository-relative and were checked against the current
workspace. Treat current source as behavior; ADRs are design records and may
be older than the present implementation.

| Interview topic | Start here | Then inspect |
|---|---|---|
| Job submission/idempotency | `backend/src/aetherflow/api/v1/jobs.py` | `backend/src/aetherflow/jobs/service.py`, `jobs/schemas.py`, `backend/tests/test_jobs.py` |
| State transitions | `backend/src/aetherflow/jobs/state_machine.py` | `jobs/service.py`, `backend/src/aetherflow/infrastructure/database/models.py` |
| Database persistence | `backend/src/aetherflow/infrastructure/database/models.py` | `infrastructure/database/session.py`, `backend/migrations/versions/` |
| Outbox creation/publication | `backend/src/aetherflow/jobs/service.py` | `jobs/outbox.py`, `infrastructure/kafka.py`, `backend/tests/test_outbox.py` |
| Kafka envelope/offset | `backend/src/aetherflow/infrastructure/kafka.py` | `backend/tests/test_kafka.py`, ADR-0011 |
| Worker claim/execute | `backend/src/aetherflow/jobs/worker.py` | `jobs/execution.py`, `backend/tests/test_phase4a.py` |
| Retry classification | `backend/src/aetherflow/jobs/retry.py` | `jobs/worker.py`, `backend/tests/test_phase6_execution_retry.py`, ADR-0015 |
| Scheduling | `backend/src/aetherflow/jobs/scheduler.py` | `jobs/service.py`, `backend/migrations/versions/0006_durable_scheduling.py`, `backend/tests/test_phase12_scheduling.py` |
| Provider boundary | `backend/src/aetherflow/jobs/execution.py` | `jobs/providers.py`, `jobs/openai.py`, `backend/tests/test_phase5_providers.py`, `test_phase9_provider.py` |
| Password/session/API key | `backend/src/aetherflow/auth/passwords.py` | `auth/tokens.py`, `auth/service.py`, `api/v1/auth.py`, `api/v1/api_keys.py`, `backend/tests/test_auth.py` |
| Role and ownership policy | `backend/src/aetherflow/auth/policies.py` | `api/v1/admin.py`, `jobs/service.py`, `backend/tests/test_phase13_admin.py` |
| API error contract | `backend/src/aetherflow/api/errors.py` | `api/v1/jobs.py`, `backend/tests/test_app.py` |
| Health and metrics | `backend/src/aetherflow/api/health.py` | `backend/src/aetherflow/observability/metrics.py`, `backend/tests/test_phase7_observability.py` |
| Redis rate limit | `backend/src/aetherflow/observability/rate_limit.py` | `infrastructure/redis.py`, `backend/tests/test_phase11_redis.py`, ADR-0020 |
| Frontend sign-in/session | `frontend/components/auth/auth-provider.tsx` | `frontend/lib/api/client.ts`, `frontend/app/login/page.tsx`, `frontend/tests/api-client.test.ts` |
| Frontend submission/list/detail | `frontend/app/(console)/submit/page.tsx` | `frontend/app/(console)/jobs/page.tsx`, `frontend/components/jobs/job-detail.tsx`, `frontend/tests/job-detail.test.tsx` |
| Frontend demo/admin | `frontend/app/demo/page.tsx` | `frontend/app/(console)/admin/page.tsx`, `frontend/tests/demo.test.tsx` |
| Backend tests and fixtures | `backend/tests/conftest.py` | Test files in `backend/tests/`, `docs/TESTING.md` |
| Frontend tests | `frontend/vitest.config.ts` | `frontend/tests/`, `frontend/package.json` |
| Migrations | `backend/migrations/versions/0001_identity_access.py` | Revisions `0002_jobs_and_idempotency.py` through `0007_demo_role.py` |
| Local process topology | `docker-compose.yml` | `.env.example`, `README.md`, `docs/ARCHITECTURE.md` |

## Quick navigation method

When asked a question, first find the route or process entrypoint, then follow
the service call, then the model/transaction, then its test. For delivery
questions, trace API commit → outbox claim → Kafka send/finalize → worker
consume/ack → state/result commit. Read the relevant migration when a
constraint or index matters. Check the test to see whether it is a fake,
SQLite, live local integration, or hosted CI result.

# Chapter 23 — Glossary and Final Revision Sheets

## Distributed-systems glossary

| Term | Meaning in this handbook |
|---|---|
| At-least-once delivery | A record may be delivered again if acknowledgement is not durably committed. |
| Idempotency key | Caller-provided key/fingerprint used to return one prior submission rather than create another job. |
| Transactional outbox | A DB row committed with business state, later relayed to a separate broker. |
| Consumer group | Consumers sharing topic partitions; each active partition is assigned to one member in the group. |
| Offset | Position in a Kafka partition; commit records consumer progress. |
| Lease | Time-bounded durable claim that can be recovered after expiry. It does not stop an external API. |
| Fencing/version check | Conditional durable update that rejects a stale state/version writer. |
| Backpressure | Limiting/controlling incoming work when downstream capacity is insufficient. |
| Poison message | A record that repeatedly cannot be processed or is invalid. |
| Retry storm | Correlated retries that overload an already unhealthy dependency. |
| Compare-and-set | Update only if the stored state/version still equals the expected value. |
| Dead letter | A terminally rejected/deferred record requiring inspection; it needs an explicit operational policy. |
| RPO / RTO | Recovery Point Objective / Recovery Time Objective; data-loss and recovery-time targets. |
| SLO / SLI | Service Level Objective / Indicator; reliability target and the measurement used to assess it. |
| IDOR | Insecure Direct Object Reference: object access is not authorized for the current principal. |
| CAS | Compare-and-set; in AetherFlow, a guarded state/version write. |
| DLQ | Dead-letter queue, a dedicated place for terminally rejected messages. |
| HA | High availability; continued service despite defined component failures. Not established by local Compose. |
| PII | Personally identifiable information; prompts and outputs may contain sensitive content. |
| TTL | Time to live; expiry duration for a token, lease, or cache entry. |

## Important state transitions

```text
ACCEPTED -> QUEUED -> RUNNING -> SUCCEEDED
                            -> RETRY_SCHEDULED -> QUEUED
                            -> FAILED
ACCEPTED / QUEUED / RUNNING / RETRY_SCHEDULED -> CANCEL_REQUESTED
ACCEPTED (scheduled and not yet activated) -> CANCELLED
CANCEL_REQUESTED -> CANCELLED | SUCCEEDED | FAILED
```

`DEAD_LETTERED` is terminal in the state machine. A future schedule begins
`ACCEPTED`; the scheduler activates it to `QUEUED`. State transitions are
version-checked. Consult `jobs/state_machine.py` for the exact permitted
edges.

## Guarantees and non-guarantees

**Can defend:** job/outbox intent is committed atomically for immediate work;
future schedules are durable in PostgreSQL; API idempotency is principal/key
scoped; dispatch is at least once; stale durable transitions are guarded by
state/version/lease logic; selected failure classes have bounded retry.

**Cannot claim:** exactly-once LLM invocation; remote cancellation; globally
ordered jobs; live-provider success; tested PostgreSQL lock races; HA/cloud
deployment; durable centralized metrics; measured throughput or latency.

## Top 25 questions to rehearse

1. What does AetherFlow solve?
2. Why asynchronous processing?
3. What happens from submit to result?
4. Why a transactional outbox?
5. What happens after Kafka acknowledges and publisher crashes?
6. Can provider execution repeat?
7. What exactly does idempotency protect?
8. How does the worker claim a job?
9. What does a lease protect, and what does it not protect?
10. Which errors retry today?
11. How are retry storms mitigated, and what is still missing?
12. What if PostgreSQL or Kafka is down?
13. How are due jobs activated and cancelled?
14. What if two schedulers contend?
15. Why Kafka instead of PostgreSQL polling?
16. Why PostgreSQL instead of a document database?
17. Why use Redis, and what happens on its outage?
18. What does API readiness mean?
19. How are users isolated from each other's jobs?
20. How is the mock provider useful?
21. What is the weakest verified engineering area?
22. What do the tests prove and not prove?
23. How would you scale after measuring?
24. Why is public deployment not claimed?
25. What would you implement next?

## One-page pre-interview cheat sheet

- **Pitch:** durable asynchronous AI jobs with outbox → Kafka → leased
  worker → provider adapter → persisted result.
- **Source of truth:** PostgreSQL. Kafka is dispatch transport. Redis is
  optional fail-open rate limiting.
- **Outbox:** job plus intent commit together; send/finalize split means
  duplicate publication is possible.
- **Delivery:** at least once; offsets are committed after durable decision.
- **Execution:** may repeat if provider acts before result commit.
- **Stale claim:** lease plus state/version checks; not a remote kill switch.
- **Retry:** current retryable categories are rate limit, timeout and
  transient provider; bounded deterministic backoff; jitter not applied.
- **Scheduler:** durable one-shot UTC timestamps; SQLite tests do not prove
  PostgreSQL race semantics.
- **Provider:** deterministic mock default, OpenAI-compatible adapter; no
  automatic provider fallback and no universal typed output schema.
- **Security:** Argon2; short-lived access token; rotating hashed refresh
  session; API-key secret hashed; ownership checks; demo is read-only.
- **Operations:** liveness is local; readiness checks PostgreSQL only;
  metrics are process-local; no bundled dashboards/alerts/OTel.
- **Verification:** 150 backend tests, 32 frontend tests at the recorded
  workspace snapshot; limited prior Compose smoke; not production proof.
- **Honesty:** no public deployment, performance result, personal incident or
  team ownership claim unless independently confirmed.
- **Best next evidence:** PostgreSQL concurrency, Kafka rebalance/restart,
  cross-process Redis and fault-injection tests.

## Explain-the-project honesty checklist

- [ ] Did I separate code from ADR intent and future proposal?
- [ ] Did I confirm this behavior in current source, not an old diagram?
- [ ] Did I say which tests used SQLite/fakes and which infrastructure ran?
- [ ] Did I avoid claiming exactly-once provider execution?
- [ ] Did I identify the publisher crash duplicate window?
- [ ] Did I explain that cancellation may not stop an in-flight provider?
- [ ] Did I avoid invented incidents, team size, traffic and benchmarks?
- [ ] Did I state my personal contribution accurately?
- [ ] Did I avoid exposing credentials or private job payloads?
- [ ] Did I describe deployment status and my real reason truthfully?
- [ ] Can I open the route, service, model, migration and test for each claim?

## Source-verification note

Project-specific statements in this handbook were checked against the local
repository source, schemas, migrations, tests, README, architecture/API/
data-flow/limitations/testing documentation, Compose configuration and ADRs.
The observed verification snapshot is dated 2026-10-07 and includes
uncommitted working-tree changes. Tests and source can change after this
snapshot. Generic distributed-systems explanations are educational context;
recommendations are proposals, not implemented behavior. No private
environment file or credential is a source for this guide.
