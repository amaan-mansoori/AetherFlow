# Chapter 20 — Interview Question Bank with Answers

## How to use the answers

Start with the spoken version; expand into the deeper explanation only when
the interviewer asks. Keep ownership statements factual: fill in the work
you personally did, and do not borrow an architecture decision as proof that
you implemented every part. “Verify” names source to open before the interview.
The avoid note flags common overclaims.

## A. Recruiter screening and project summary

### A1. What is AetherFlow?

**Spoken:** “It is a local-first asynchronous AI job orchestration project:
jobs are persisted, dispatched through an outbox and Kafka, executed by
workers through a provider boundary, and inspected in a web console.”

**Deeper:** PostgreSQL is authoritative; Kafka carries versioned dispatch
references; Redis is only optional rate limiting. Its value is the lifecycle
and failure-boundary engineering, not an AI chat UI. It is not a public
production service or benchmark.

**Likely follow-up:** What happens between `POST /jobs` and a result?
**Avoid:** “It handles millions of requests” or “it is production-proven.”
**Verify:** `docs/ARCHITECTURE.md`, `docs/DATA-FLOW.md`, README.

### A2. Give a 30-second project pitch.

**Spoken:** Use the 30-second overview in Chapter 1, then offer one concrete
trade-off: outbox durability permits duplicate dispatch after a crash.
**Deeper:** Name the API transaction, publisher, consumer, state/version
checks, and the at-least-once/non-exactly-once boundary. Tailor the final
sentence to your actual contribution rather than claiming team-wide work.

**Likely follow-up:** Which part did you personally own?
**Avoid:** Reciting every technology name without a problem/guarantee.
**Verify:** Chapter 1 and your own commit history/notes.

## B. Individual contribution and ownership

### B1. What did you personally build?

**Spoken:** “I worked on [accurate components]. The repository shows how those
components behave; I can walk through [specific source/test] and explain my
decisions.”

**Deeper:** Separate authored code, design, debugging, tests, documentation,
and prior work. This repository audit cannot determine the author's personal
contribution or team context. Give a bounded example you can defend from your
own history.

**Likely follow-up:** Which decision would you change, and why?
**Avoid:** Claiming sole authorship of the entire system without evidence.
**Verify:** Your own commit/PR history and files you can explain line by line.

### B2. Describe an engineering challenge you faced.

**Spoken:** Do not invent an incident. Select a real experience you can
substantiate; if using this project, present the outbox crash window as a
design failure scenario, not as something you personally experienced.

**Deeper:** State context, observed evidence, alternatives, change, and
verification. A code-backed scenario can explain the dual write and duplicate
publication without pretending it happened in production.

**Likely follow-up:** What log or test proved your fix?
**Avoid:** Converting a hypothetical failure timeline into a personal
debugging story.
**Verify:** `docs/TESTING.md`, relevant diff/PR, `jobs/outbox.py`.

## C. Problem statement and requirements

### C1. Why make inference asynchronous?

**Spoken:** “It separates request acceptance from unpredictable provider
latency. The client receives a durable job ID and can inspect status later.”

**Deeper:** Asynchrony reduces coupling to HTTP/proxy timeouts and allows
independent worker capacity, but adds durable state, delivery, retries,
visibility and cancellation complexity. It is not automatically simpler or
lower latency end-to-end.

**Likely follow-up:** When would a synchronous call be better?
**Avoid:** Saying asynchronous means instant completion.
**Verify:** `jobs/service.py`, `api/v1/jobs.py`, Chapter 2.

### C2. Which requirements are actually implemented?

**Spoken:** “Durable submission, idempotency, outbox dispatch, Kafka workers,
selected retries, one-shot scheduling, auth/ownership, and status history are
implemented. Recurring schedules, exactly-once execution and production
deployment are not claimed.”

**Deeper:** Separate current code from generic needs and proposed future work.
For example, durable retry intent exists, but no operator replay UI/API does.

**Likely follow-up:** Which missing feature blocks production first?
**Avoid:** Treating an item in an architecture diagram as shipped.
**Verify:** `docs/KNOWN-LIMITATIONS.md`, code and migration path.

## D. Architecture and component responsibilities

### D1. Walk through the architecture.

**Spoken:** “The API commits job plus outbox intent to PostgreSQL; a
publisher sends versioned dispatch to Kafka; a worker claims and executes;
the scheduler activates due jobs; the console reads persisted status.”

**Deeper:** Kafka is not the lifecycle source of truth. PostgreSQL owns the
state machine, attempts and results. The scheduler writes due intent but
doesn't publish. Redis does not participate in job correctness.

**Likely follow-up:** Which process can be unavailable without rejecting a
valid submission?
**Avoid:** Calling these modules separately deployed microservices by default.
**Verify:** Compose file, app entrypoints, `docs/ARCHITECTURE.md`.

### D2. Why separate publisher, scheduler, worker and API processes?

**Spoken:** “They have different loops and dependencies, while sharing one
modular backend and database contract.”

**Deeper:** Process separation allows different lifecycle and scaling knobs;
the trade-off is more configuration, connections, supervision and deployment
coordination. It is process isolation, not evidence of independent service
ownership or separate data stores.

**Likely follow-up:** What would you consolidate for a tiny deployment?
**Avoid:** Saying microservices are inherently more scalable.
**Verify:** `backend/src/aetherflow`, Compose services, ADR-0017.

## E. Python and FastAPI

### E1. Why FastAPI rather than Django or Flask?

**Spoken:** “FastAPI fits a typed async API with Pydantic validation and
generated OpenAPI. I would choose based on project needs, not claim it is
universally better.”

**Deeper:** Django REST Framework provides more integrated admin/auth and
conventions; Flask can be lighter but leaves more decisions to extensions.
The inspected repository does not document a head-to-head framework
evaluation.

**Likely follow-up:** What would Django simplify here?
**Avoid:** Attributing undocumented alternatives to original decision history.
**Verify:** `backend/pyproject.toml`, API app/routes, ADR directory.

### E2. How do async Python and SQLAlchemy fit together?

**Spoken:** “FastAPI route dependencies provide an async session; service
functions own transactions, and provider/Kafka I/O is kept outside DB
transactions.”

**Deeper:** An async function only helps when awaited I/O is genuinely
nonblocking. A per-process connection pool must be included in replica
capacity; blocking CPU work would still require separate treatment.

**Likely follow-up:** Can an async endpoint create unbounded concurrency?
**Avoid:** Equating `async` with unlimited throughput.
**Verify:** `infrastructure/database/session.py`, route dependencies, worker.

## F. REST API design and validation

### F1. How does the submission API validate input?

**Spoken:** “Pydantic schemas bound fields, reject extra fields on the
request, normalize timezone-aware schedules to UTC, and reject
credential-like configuration.”

**Deeper:** The schema is an API boundary, not a promise that every model or
provider supports every shape. Domain services separately validate
idempotency and state. Validation errors follow the public structured error
contract.

**Likely follow-up:** Where would you add a per-job typed output schema?
**Avoid:** Calling arbitrary dictionary output a validated business schema.
**Verify:** `jobs/schemas.py`, `api/errors.py`, provider `ExecutionOutcome`.

### F2. How does idempotency work?

**Spoken:** “The caller supplies an idempotency key. It is scoped to the
principal and paired with a request fingerprint; same key/same request returns
the prior job, different payload conflicts.”

**Deeper:** The unique database constraint handles concurrent submissions.
The idempotency record and job creation are committed together. This protects
HTTP submission, not provider execution or Kafka publication.

**Likely follow-up:** What if two same-key requests race?
**Avoid:** Saying the key guarantees one provider call.
**Verify:** `jobs/service.py`, `idempotency_records` model/migration/tests.

## G. PostgreSQL, transactions, indexes and migrations

### G1. Which consistency boundary is PostgreSQL responsible for?

**Spoken:** “It is the source of truth for job state, idempotency, attempts,
results and the outbox. A transaction couples job acceptance to dispatch
intent.”

**Deeper:** State/version predicates and constraints guard races; database
transactions do not include Kafka or the LLM. Migrations are versioned with
Alembic, and due/outbox/owner/lease indexes support their query paths.

**Likely follow-up:** Which writes are deliberately separate transactions?
**Avoid:** Claiming a PostgreSQL transaction spans Kafka.
**Verify:** `infrastructure/database/models.py`, migrations, service/outbox.

### G2. Why PostgreSQL instead of MongoDB?

**Spoken:** “The project needs relational ownership, unique idempotency,
transactional outbox writes, and conditional state transitions; PostgreSQL
fits those boundaries.”

**Deeper:** MongoDB can support transactions and may fit document-centric
schemas, but choosing a document store does not remove concurrency or
dual-write problems. No repository evidence shows a MongoDB prototype or
original bake-off.

**Likely follow-up:** What data might be document-shaped?
**Avoid:** “MongoDB cannot do transactions.”
**Verify:** models, constraints, migration chain and ADRs.

## H. Kafka

### H1. Why Kafka instead of a database-backed queue?

**Spoken:** “Kafka provides a durable partitioned dispatch stream and consumer
groups; that can isolate API acceptance from workers. It costs a broker and
operational complexity.”

**Deeper:** A PostgreSQL queue could be simpler at modest scale and share
transaction boundaries. Kafka is justified only if replay/partition/consumer
requirements outweigh DB polling. ADRs record the Kafka direction, not a
universal superiority claim.

**Likely follow-up:** What if traffic never needs Kafka-scale throughput?
**Avoid:** Citing benchmarked throughput that does not exist.
**Verify:** ADR-0003/0005/0012, dispatch adapter, Compose broker.

### H2. How are offsets committed?

**Spoken:** “Auto-commit is disabled; the worker acknowledges/commits after a
durable processing decision. Failure before that can cause redelivery.”

**Deeper:** State/version checks and constraints make duplicate messages
largely safe for durable state, but cannot make the external provider call
exactly once.

**Likely follow-up:** What if the DB commits but offset commit fails?
**Avoid:** Saying an offset equals a completed provider transaction.
**Verify:** `infrastructure/kafka.py`, worker runner and tests.

## I. Transactional outbox

### I1. Why use an outbox?

**Spoken:** “It commits job state and dispatch intent atomically in
PostgreSQL, so an API crash after commit cannot silently lose the intent.”

**Deeper:** A separate publisher leases rows, sends outside the transaction,
then finalizes. This removes one lost-message window but leaves possible
duplicate publication after broker acknowledgement.

**Likely follow-up:** Why not publish inside the DB transaction?
**Avoid:** “The outbox gives exactly-once delivery.”
**Verify:** `jobs/service.py`, `jobs/outbox.py`, ADR-0012.

### I2. What if publisher crashes after Kafka accepts a message?

**Spoken:** “PostgreSQL may still show the row unpublished. After lease
expiry it can be sent again; the consumer must tolerate a duplicate.”

**Deeper:** Kafka and PostgreSQL do not share an atomic commit. Producer
idempotence does not cover a new publish attempt after the process restarts.
The worker checks persisted state/version and the external inference may
still execute more than once in a different crash window.

**Likely follow-up:** What state prevents stale work from overwriting newer
work?
**Avoid:** Suggesting the window can be eliminated by a longer lease.
**Verify:** Outbox lease predicates, Kafka producer, worker claim.

## J. Distributed systems and consistency

### J1. What happens if PostgreSQL is unavailable?

**Spoken:** “The API cannot commit a new durable job and readiness should
fail. Publisher/scheduler/worker cannot make durable decisions; Kafka
messages should remain unacknowledged if processing fails before persistence.”

**Deeper:** Exact client error/retry behavior depends on the route/driver and
runtime, so verify logs and error handlers. Existing jobs remain in Kafka or
the outbox, but recovery needs PostgreSQL restored. Do not claim every process
has a tested database-outage runbook.

**Likely follow-up:** What does the caller do after a timeout?
**Avoid:** Retrying a non-idempotent POST without its original key.
**Verify:** readiness, SQL session lifetime, worker exception/ack path.

### J2. What guarantees does the system not provide?

**Spoken:** “No exactly-once provider execution, guaranteed remote
cancellation, globally ordered jobs, high availability, or production SLO is
claimed.”

**Deeper:** Dispatch is at least once. Database state transitions use
version/state checks; idempotent HTTP creation is separately supported.
External effects and local commits cannot be atomically coordinated.

**Likely follow-up:** How do you know a job is truly complete?
**Avoid:** Treating Kafka acknowledgement or a provider HTTP 200 alone as
durable completion.
**Verify:** result persistence, terminal transition, stale-lease recovery.

## K. Worker leases, retries and recovery

### K1. Can a job execute more than once?

**Spoken:** “Yes. A worker can call the provider, crash before persisting the
result, and the system cannot know whether the external work happened.”

**Deeper:** Kafka redelivery and outbox duplicates are distinct from execution
retry. Durable state/version guards and unique result/attempt constraints
protect database invariants, not the external provider side effect. A
provider-supported idempotency key could narrow the risk.

**Likely follow-up:** What would you need for effectively-once effects?
**Avoid:** “Kafka exactly once means provider exactly once.”
**Verify:** worker execution order, result constraints, provider API contract.

### K2. What prevents a stale worker from overwriting a newer result?

**Spoken:** “A lease owner/expiry plus job state/version checks and
compare-and-set updates reject stale durable transitions.”

**Deeper:** This fences writes only where the DB predicate is applied. A
provider request already sent cannot be recalled. Recovery reconciles by
result presence: result means `SUCCEEDED`; no result after expired lease means
`FAILED`.

**Likely follow-up:** Is the lease a fencing token for the provider?
**Avoid:** Saying lease expiry forcibly terminates a remote request.
**Verify:** claim/finalize queries and stale execution recovery.

### K3. How do you avoid retry storms?

**Spoken:** “Retries are bounded and capped, but the current delay is
deterministic and configured jitter is not applied. Jitter and provider
concurrency controls are improvements.”

**Deeper:** Retries only cover rate-limit, timeout and transient-provider
categories. Retry budget and delay are separate from outbox publication
retry. Measure correlated failures and provider quota before changing policy.

**Likely follow-up:** Would you honor `Retry-After`?
**Avoid:** Claiming exponential backoff has jitter when it does not.
**Verify:** `jobs/retry.py`, settings/schema, tests and ADR-0015.

## L. Scheduling and cancellation

### L1. What if two schedulers pick the same due job?

**Spoken:** “The scheduler claims due rows with database locking and then
uses state/version conditions; the activation event and outbox row are
transactional.”

**Deeper:** `SKIP LOCKED`/compare-and-set are intended to avoid two successful
activations. Current SQLite tests do not prove PostgreSQL multi-process lock
behavior; test that with concurrent PostgreSQL transactions.

**Likely follow-up:** How do cancellation and due activation race?
**Avoid:** Presenting tests on SQLite as a production locking proof.
**Verify:** `jobs/scheduler.py`, schedule indexes, scheduling tests.

### L2. What does cancellation mean?

**Spoken:** “For a still-accepted scheduled job, current code cancels
directly. For work already in the execution path, cancellation is a request
and does not guarantee the provider call stops.”

**Deeper:** Scheduler and cancellation race through durable state/version.
Already-published records for terminal jobs are stale no-ops. A running
provider may still complete and its outcome can win according to the current
state transition policy.

**Likely follow-up:** How would you implement hard cancellation?
**Avoid:** Promising remote cancellation without provider support.
**Verify:** `jobs/service.py`, state machine, current regression tests.

## M. Redis and rate limiting

### M1. Why use Redis/Valkey?

**Spoken:** “Only for optional atomic fixed-window API rate-limit counters
shared by API instances. It is not a job cache, queue or correctness store.”

**Deeper:** Auth and general API routes have separate classes; a public API
key ID or client host is hashed for key construction. Redis failure is
observed and fails open, which preserves availability but removes
rate-limit enforcement temporarily. Valkey protocol compatibility does not
mean the project tested a Valkey deployment.

**Likely follow-up:** Why fail open rather than fail closed?
**Avoid:** Claiming Redis is required to process a job correctly.
**Verify:** `observability/rate_limit.py`, `infrastructure/redis.py`,
ADR-0020.

## N. AI provider abstraction and deterministic mocks

### N1. Why abstract the provider?

**Spoken:** “The executor boundary separates provider-specific transport and
failure normalization from job lifecycle logic and makes tests deterministic.”

**Deeper:** Mock is the default; an OpenAI-compatible HTTP adapter is
implemented. Normalized outcomes are dictionaries with metadata, not a
universal strongly typed output schema. No automatic provider fallback is
implemented.

**Likely follow-up:** Which provider-specific behavior should remain visible?
**Avoid:** Calling the interface a guarantee that providers are interchangeable.
**Verify:** `jobs/execution.py`, `providers.py`, `openai.py`, provider tests.

### N2. How do you test without a live LLM?

**Spoken:** “Use the deterministic mock for lifecycle tests and mock HTTP
transport for the OpenAI-compatible adapter's request/error mapping.”

**Deeper:** This proves local input/output and normalization paths, not live
credentials, vendor availability, current quota or real model quality.
External contract tests need safe credentials and an opt-in isolated
environment.

**Likely follow-up:** How do you validate generated structured output?
**Avoid:** Saying the provider always returns correct JSON.
**Verify:** provider tests and `ExecutionOutcome` validation.

## O. Next.js and frontend/API integration

### O1. How does the UI receive status updates?

**Spoken:** “The detail view polls the API about every ten seconds while the
tab is visible and the job is not terminal; there is no WebSocket path.”

**Deeper:** It aborts requests on unmount, pauses polling when hidden, resumes
on visibility, and exposes loading/error/cancel states. Polling trades
freshness for simplicity and read load.

**Likely follow-up:** When would you switch to SSE?
**Avoid:** Describing polling as real-time push.
**Verify:** `components/jobs/job-detail.tsx`, API client, UI tests.

### O2. Where is the access token stored?

**Spoken:** “The frontend client keeps the short-lived access token in memory
and uses an HttpOnly refresh cookie with credentialed requests.”

**Deeper:** Refresh rotation and current-user checks are server concerns;
browser state is not authorization. Verify exact cookie flags and CORS
configuration for the deployed environment.

**Likely follow-up:** What happens after a page reload?
**Avoid:** Claiming the bearer token is in local storage.
**Verify:** `auth-provider.tsx`, `lib/api/client.ts`, auth routes.

## P. Authentication, authorization and security

### P1. How do you prevent a user from reading another user's job?

**Spoken:** “The authenticated principal is passed into service queries, and
ordinary lookups are owner-scoped; admins use separate role-protected
operations.”

**Deeper:** Object-level authorization must apply to detail, events, attempts
and cancellation, not merely hide a UI link. Tests include private-job
isolation.

**Likely follow-up:** How would you test IDOR?
**Avoid:** Trusting a UUID's unguessability.
**Verify:** `jobs/service.py`, dependencies, auth/API tests.

### P2. How would you secure an exposed demo?

**Spoken:** “Do not expose shared credentials casually. Use a read-only
provisioned demo, isolate secrets, add quotas/rate limits, TLS and monitoring,
and protect provider spend.”

**Deeper:** Current demo is opt-in and read-only. Redis limiting fails open;
public deployment requires abuse controls and an explicit secret/data policy.
Email verification/password recovery are absent.

**Likely follow-up:** What if Redis is down?
**Avoid:** Calling a shared demo identity equivalent to production onboarding.
**Verify:** demo provisioning, role policy, rate limiter, CORS/settings.

## Q. Testing, debugging and quality

### Q1. What does the current test suite prove?

**Spoken:** “It proves deterministic service/API/frontend behavior through
SQLite and fakes, plus a limited prior local Compose smoke path; it does not
prove PostgreSQL lock races or production availability.”

**Deeper:** State the dated counts only with the observed environment and
warnings. Fake boundaries let tests target failure classification and
contracts, but real broker rebalance, cross-process Redis and restart tests
remain gaps.

**Likely follow-up:** What integration test would you add first?
**Avoid:** “All tests passing means production-ready.”
**Verify:** `docs/TESTING.md`, backend tests, frontend Vitest scripts.

### Q2. How would you debug a regression?

**Spoken:** “Reproduce with a focused test, identify which durable boundary
failed, correlate request/job IDs, inspect state/version/attempt/outbox, then
add a regression test.”

**Deeper:** Avoid inferring a cause from a dashboard alone. For asynchronous
work, follow persisted evidence from API commit through publication, offset,
claim, provider call and result.

**Likely follow-up:** Which test isolates this layer?
**Avoid:** Editing retry timing before identifying the failure category.
**Verify:** request logging, event/attempt APIs, test layout and source flow.

## R. Docker and local development

### R1. What does Compose provide?

**Spoken:** “PostgreSQL, Kafka, Redis, migrations and separate API, publisher,
scheduler and worker processes; the Next.js dev server runs separately.”

**Deeper:** Health checks and environment examples aid local startup, but
Compose is not a production deployment or HA broker/database. Protect local
data volumes; a smoke test should not casually reset persisted state.

**Likely follow-up:** Which service must be ready before the API?
**Avoid:** Saying the Compose stack proves cloud deployment.
**Verify:** `docker-compose.yml`, `.env.example` only, README instructions.

### R2. How do you handle local secrets?

**Spoken:** “Use the documented local environment mechanism and example
template; keep actual `.env` values out of source control and logs.”

**Deeper:** Provider secrets are runtime config, not job payload. Never read
or print a real secret to demonstrate configuration. Rotate credentials if
they are exposed.

**Likely follow-up:** How do you know a secret is not tracked?
**Avoid:** Pasting a real environment file into a terminal transcript.
**Verify:** `.gitignore`, `.env.example`, settings; never open `.env`.

## S. Observability and incident diagnosis

### S1. How would you debug jobs stuck in `QUEUED`?

**Spoken:** “Follow the dispatch path: outbox row and publication state,
Kafka reachability/lag, consumer assignment, worker logs, then job version
and state.”

**Deeper:** If still `ACCEPTED`, distinguish immediate unpublished work from
a future scheduled job. Metrics reset on restart and are process-local; read
the durable rows and logs too.

**Likely follow-up:** What if Kafka is healthy but no worker owns a partition?
**Avoid:** Assuming API readiness means end-to-end processing is healthy.
**Verify:** job/outbox detail/admin endpoints, broker group and process logs.

### S2. What does readiness actually mean?

**Spoken:** “API readiness checks PostgreSQL, while liveness is
dependency-free. It does not certify Kafka, Redis, or the LLM.”

**Deeper:** A production deployment may need role-specific probes for
publisher/worker/scheduler and queue progress, while avoiding a probe that
makes transient provider failure restart every process.

**Likely follow-up:** Would you put every dependency in readiness?
**Avoid:** Equating a 200 health response with a successful job.
**Verify:** `api/health.py`, Compose health checks, `docs/TESTING.md`.

## T. Scalability and performance

### T1. How would you scale to a million jobs?

**Spoken:** “First benchmark the workload and backlog behavior. Then size
partitions/workers/database pools, bound concurrency, index/retain hot tables,
and monitor queue age and provider quota.”

**Deeper:** A job count alone says little: arrival rate, payload size,
execution time, retention, retry rate and SLO determine capacity. Current
worker loop is sequential per consumer; adding instances is limited by topic
partitions and database/provider capacity. No benchmark supports a numeric
claim.

**Likely follow-up:** What is the first likely bottleneck?
**Avoid:** Giving a jobs-per-second figure without a reproducible test.
**Verify:** Compose partition count, pool settings, metrics, benchmark status.

### T2. What would you measure?

**Spoken:** “End-to-end acceptance-to-terminal latency, oldest outbox age,
Kafka lag, schedule lateness, provider latency/errors, DB pool/locks, and
retry rate.”

**Deeper:** Break latency by stage, track percentile/error distributions and
resource usage, and include degraded runs. Current metrics are local and
there is no benchmark or bundled scraper/alerting.

**Likely follow-up:** How do you prevent metric-cardinality explosions?
**Avoid:** Instrumenting labels with raw user/job IDs.
**Verify:** `observability/metrics.py`, current metrics exposition.

## U. Technology choices and alternatives

### U1. Why PostgreSQL rather than a document store?

**Spoken:** “The transaction and relational constraints around job ownership,
idempotency, state transitions and outbox are central. PostgreSQL is a
straightforward fit.”

**Deeper:** Document flexibility could help variable input/output payloads,
but those are JSON fields inside a relational lifecycle. A storage change
should follow measured access patterns, not schema fashion.

**Likely follow-up:** What if payloads grow very large?
**Avoid:** Saying one database is always better.
**Verify:** models, indexes, query paths, migration records.

### U2. When would you remove Kafka?

**Spoken:** “If measured load and replay/consumer needs do not justify broker
operations, a PostgreSQL-backed queue could reduce components.”

**Deeper:** Compare operational cost, transaction/locking contention,
throughput, retention/replay and delivery semantics using an actual workload.
No original alternative benchmark is documented.

**Likely follow-up:** What behavior must remain invariant after migration?
**Avoid:** Treating a technology count as architecture quality.
**Verify:** ADRs and dispatch interface.

## V. Deployment, hosting costs and operational readiness

### V1. Why is there no public deployment?

**Spoken:** “I can verify a local Compose setup and limited local smoke path,
but not a public production deployment. I would state my actual reason
directly rather than invent one.”

**Deeper:** Hosting full stateful infrastructure has cost, security, backup,
secrets and reliability obligations; those are valid considerations, not
confirmed personal motivation. Explain what deployment would require.

**Likely follow-up:** What evidence can you provide instead?
**Avoid:** Claiming cost or time was the reason without knowing it.
**Verify:** Deployment manifests, cloud histories, your actual explanation.

### V2. What is needed before public exposure?

**Spoken:** “Managed secrets, TLS, backup/restore, durable monitoring,
quotas/abuse controls, production PostgreSQL/Kafka behavior tests, and an
operational replay/incident policy.”

**Deeper:** Also define retention/deletion, data residency, SLOs, migration
strategy, cost limits and provider terms. A successful container start alone
does not address these.

**Likely follow-up:** How would you protect the demo provider budget?
**Avoid:** Calling local Compose production-ready.
**Verify:** `docs/KNOWN-LIMITATIONS.md`, ADR-0017, security settings.

## W. Weaknesses, limitations and lessons

### W1. What is the weakest engineering decision?

**Spoken:** “A defensible weakness is that failure recovery is tested mostly
with SQLite/fakes while PostgreSQL locking and Kafka rebalances are not
verified. Another is deterministic retry backoff without applied jitter.”

**Deeper:** Name the specific evidence and propose a bounded improvement:
PostgreSQL concurrency tests and a tested jitter/retry-after policy. Choose
the weakness you understand and can defend.

**Likely follow-up:** Why was that trade-off accepted?
**Avoid:** Calling a documented limitation “fixed” without code/test evidence.
**Verify:** `docs/TESTING.md`, `docs/KNOWN-LIMITATIONS.md`, retry source.

### W2. What would you redesign with another month?

**Spoken:** “I would add PostgreSQL/Kafka failure-injection integration
coverage, test restart/rebalance recovery, add durable external
observability, and reconcile documented retry policy with actual behavior.”

**Deeper:** Prioritize a reliability gap over adding a fashionable component.
Scope the work with measurable acceptance criteria and preserve the local
mock workflow.

**Likely follow-up:** What would you deliberately not add?
**Avoid:** Promising a rewrite or a benchmark outcome before measuring.
**Verify:** gap list in testing/limitations and ADR/source discrepancies.

## X. Behavioral follow-ups and ownership

### X1. Tell me about a disagreement or a decision you changed.

**Spoken:** Use a real example from your experience. This repository alone
does not establish that a disagreement or personal reversal occurred.

**Deeper:** Explain the competing constraints, evidence, decision owner,
result, and what you learned. A technical alternative comparison can be
discussed as retrospective analysis, but not dressed up as a real debate.

**Likely follow-up:** What evidence changed your mind?
**Avoid:** Fabricating a team, incident, or stakeholder.
**Verify:** Your actual notes, reviews, or commit history.

### X2. How do you know this project is yours to discuss?

**Spoken:** “I can trace the implementation, explain what I personally
contributed, identify what I did not build, and show tests and limitations.”

**Deeper:** Interviewers value understanding and ownership more than claiming
every technology. Walk through code, explain failure windows, and be clear
about the unverified deployment/performance dimensions.

**Likely follow-up:** Which file would you open first?
**Avoid:** Claiming personal implementation facts inferred only from a
repository snapshot.
**Verify:** Source navigation in Chapter 22 and your contribution record.
