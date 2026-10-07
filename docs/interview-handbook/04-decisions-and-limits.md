# Chapter 16 — Technology Choices and Alternatives

This is a **retrospective** comparison unless an ADR below is explicitly
cited. Do not say a candidate technology was considered during original
development without repository history or a decision record supporting that
statement.

| Technology | Role and fit in this project | Benefits | Costs / alternatives and when switching is justified |
|---|---|---|---|
| **FastAPI** | Async HTTP API, Pydantic validation, OpenAPI; useful for typed API/service boundaries. | Concise routes, generated schema, async ecosystem. | Django REST Framework brings integrated admin/auth conventions; Flask is smaller but leaves more conventions to assemble. Retrospective options; switch only if product needs justify migration. |
| **Next.js** | React console with App Router and typed client. | Routing/build ecosystem and React components in one app. | Vite SPA is simpler when server rendering/framework routing is not useful. Not an evidenced original comparison. |
| **PostgreSQL** | System of record, transactions, locks, constraints, due/outbox polling. | Strong relational constraints and transaction semantics central to outbox consistency. | MongoDB could fit document-centric flexible data, but relational ownership, idempotency and transaction/query needs are natural here. ADRs support PostgreSQL as durable system of record; they do not establish a MongoDB bake-off. |
| **Kafka** | Versioned dispatch topic and consumer group. | Durable partitioned log, replay/consumer-group model, independent publisher/worker processes. | PostgreSQL queue is simpler at modest load; RabbitMQ/managed queues may fit command semantics/operations better. Kafka rationale exists in ADR-0003/0005/0012/0017; no claim that alternatives were all tested. |
| **Redis** | Optional fixed-window rate limiting only. | Shared atomic counter boundary across API processes. | PostgreSQL rate-limit table is simpler but writes hot rows; gateway/managed limiter shifts operations. ADR-0020 documents coordination and rate-limit intent. Redis is not authoritative for jobs. |
| **Docker Compose** | Local PostgreSQL/Kafka/Redis/API/publisher/scheduler/worker/migrations environment. | Reproducible local dependencies and explicit process topology. | Testcontainers can isolate test dependencies; a managed dev stack reduces local resource use. Compose is not a production orchestrator. |
| **Pydantic** | Request, settings and response validation/serialization. | Runtime boundary validation plus schema integration. | Dataclasses/attrs are lighter for internal values but need separate parsing; Pydantic is already part of FastAPI's contract. |
| **SQLAlchemy async** | ORM, sessions, async DB transactions/queries. | Relationships, explicit transactions, typed persistence boundary. | Direct SQL/asyncpg gives more query control and less ORM behavior; choose where measured complexity warrants it. |
| **Alembic** | Versioned relational schema migrations. | Reviewable ordered upgrades/downgrades tied to SQLAlchemy metadata. | Framework-native migration systems are reasonable if framework changes; raw DDL scripts can suit a tiny schema but lack richer migration conventions. |
| **pytest / pytest-asyncio** | Backend unit/API/service test runner. | Fixture ecosystem, parametrization, async testing. | unittest is built-in and adequate for smaller suites; pytest fixtures fit the existing suite. |
| **Vitest / Testing Library** | Frontend component and client tests in jsdom. | Fast Vite-aligned runner and user-facing interaction tests. | Jest is mature, but changing brings migration cost without evidence of a current limitation. |
| **Provider abstraction** | `JobExecutor` boundary, mock executor, OpenAI-compatible adapter. | Tests avoid live credentials; business lifecycle does not embed provider SDK calls. | Direct SDK is simpler for a single throwaway provider, but couples retries/contracts to vendor. Abstraction is worthwhile while normalized behavior is needed; avoid over-generalizing provider-specific features. |

## Alternatives considered versus alternatives worth considering

ADRs state concrete rationale for Kafka/dispatch, at-least-once processing,
outbox, recovery, metrics, deployment and Redis. They are design intent, not
proof every alternative was prototyped or load-tested. FastAPI and Next.js do
not have a documented head-to-head evaluation in the inspected ADR set.
Frame non-documented options as retrospective alternatives, not project
history.

# Chapter 17 — Engineering Challenges and Trade-Offs

## Documented design complexity

| Complexity | Why it matters | Existing approach | Residual risk / interviewer probe |
|---|---|---|---|
| PostgreSQL/Kafka dual write | Either system can accept while the other fails. | Transactional outbox; separate publisher leases/finalization. | Kafka ack before DB mark can duplicate. “How do you prove no lost intent?” |
| At-least-once delivery | Consumer may see a record again. | Offset after durable decision; state/version guards, unique attempt/result. | Provider side effect can repeat. “What is idempotent here and what is not?” |
| External call versus state | Provider result cannot join local DB transaction. | Call outside transaction; lease and reconciliation by durable result. | Crash after provider success but before result means ambiguity. |
| Scheduling race | Multiple pollers or cancellation can contend. | DB locks, due-state filter, compare-and-set; current scheduled cancellation directly terminal. | PostgreSQL race behavior not proved by SQLite suite. |
| Configuration surface | Multiple local processes depend on URLs, secrets, topic and provider settings. | Pydantic settings and Compose examples/health checks. | A healthy API does not prove worker/broker/provider configuration. |
| Test determinism | Live external services make CI flaky and expensive. | SQLite and fakes for default tests; limited local Compose smoke. | Fakes cannot prove broker/database concurrency behavior. |
| Observability scope | Per-process metrics disappear on restart. | Prometheus exposition and structured logs. | No collector, dashboards or alerts are bundled. |

## Current source-versus-design discrepancy

ADR-0015 describes `UNEXPECTED` internal failures as retry candidates, while
the present `jobs/retry.py` retryable set contains only rate-limit, timeout,
and transient-provider categories. The handbook reports current executable
behavior and marks the ADR as older intent. No change to runtime retry
behavior was made for this documentation task.

Older ADR text also differs from current behavior for cancellation of a
scheduled job while still `ACCEPTED`: the current working tree transitions it
directly to `CANCELLED`; ADR-0021 describes the earlier flow. Likewise,
ADR-0003 language about lifecycle-event topics is older than the current
dispatch-only Kafka message path. The source and current flow docs are the
behavioral truth; ADRs explain prior design intent.

## Historical facts versus hypothetical scenarios

The repository documents architecture decisions and test scope, not personal
production incidents or a historical debugging diary. The outbox crash
window, broker outage, stale worker and cancellation race described here are
failure scenarios derived from code boundaries, not claims that the author
personally experienced them. The observed audit items are the retry
discrepancy, stale ADR wording, process-local metrics, and gaps explicitly
listed in `docs/KNOWN-LIMITATIONS.md` / `docs/TESTING.md`.

## A defensible lesson

The valuable lesson is to phrase guarantees at the correct boundary. An
outbox makes database intent durable; it does not make cross-system delivery
exactly once. A lease protects a database claim; it does not stop an external
provider. A passing fake-backed test verifies domain behavior; it does not
prove PostgreSQL locking. An interviewer is likely to probe exactly those
distinctions.

# Chapter 18 — Scalability and Performance

No reproducible throughput or latency benchmark is present. Do not invent
jobs/second, p95, cost-per-job or concurrency claims. A benchmark needs the
source revision, workload mix, input sizes, provider/mock choice, host,
database/broker configuration, process counts, duration, warmup, percentiles,
error rate and resource use.

## Scaling dimensions

- **Workers:** increase consumer instances up to topic partition count and
  safe provider/database capacity. Current per-instance loop is sequential.
  Add bounded concurrency only after defining per-job ordering, database
  sessions, shutdown, provider quota and lease renewal semantics.
- **Kafka:** partitions permit parallelism and per-key ordering; changing
  partition count can remap keys. Size for consumers and throughput, then
  validate rebalance behavior and broker durability/replication.
- **PostgreSQL:** likely bottleneck candidates include hot job-row updates,
  outbox eligibility scans, growing event/attempt tables, indexes, and
  connection count. Use query plans, lock/wait metrics and realistic
  retention tests before denormalizing or splitting services.
- **Connections:** calculate API + worker + publisher + scheduler pools across
  all replicas. A process-replica scale-out can exhaust the database before
  CPU is saturated.
- **Backlog/backpressure:** measure oldest outbox age, Kafka lag, due-schedule
  lateness, active lease age, provider latency and retry rate. Bound producer
  batches and worker concurrency. A faster enqueue path that lets a backlog
  grow without limit is not safe scaling.
- **Retry storms:** deterministic capped delay can synchronize retries.
  Jitter is accepted but not applied in the present policy; implementing and
  testing jitter, retry-after hints, circuit breaking or per-provider
  concurrency is future work, not current behavior.
- **Caching/rate limiting:** Redis is only optional fixed-window request
  limiting. There is no result/job cache. Cache only if measured read load and
  invalidation semantics justify it.
- **Dead lettering:** outbox permanent failure and `DEAD_LETTERED` state exist
  as concepts, but there is no operator replay endpoint/UI. A future DLQ
  workflow needs authenticated review, reason, idempotency, audit and safe
  version regeneration.

## Measurement plan

1. Define a representative request/output distribution and target objectives.
2. Benchmark API persistence with PostgreSQL and no provider calls.
3. Benchmark outbox/Kafka/worker independently and end-to-end.
4. Sweep partitions, worker count, pool size, batch size and poll intervals.
5. Inject broker/database/provider errors; measure recovery and duplicate
   effects, not just successful throughput.
6. Record bottlenecks and repeatable scripts; add only observed results to
   README.

# Chapter 19 — Deployment Decision and Honest Limitations

## What is and is not verified

The repository provides a reproducible local Compose topology and a Next.js
development setup. A limited local smoke check was observed through
PostgreSQL, Kafka, publisher, scheduler and worker for mock success, retry
exhaustion and a due schedule. The stack pre-existed and was not freshly
rebuilt against every current working-tree change. Tests and `docker compose
config --quiet` passed in the recorded workspace. These facts do not equal a
public production deployment, high availability, cloud integration,
cross-process recovery guarantee or real-provider success.

The project owner has not confirmed why there is no verified public
deployment. Do **not** attribute it to cost, secrets, time, or any personal
reason unless that is true and the author confirms it. A responsible,
non-invented answer is:

> I can show the repository, the local Compose environment, the deterministic
> tests, and the parts of the infrastructure flow that were exercised. I do
> not have evidence of a public production deployment, so I do not present it
> as production-operated. If I deploy it publicly, I first need to decide how
> to protect provider credentials and demo access, provision managed stateful
> dependencies, set backups/retention and TLS, add external scraping/alerts,
> and validate restart and concurrency behavior. The actual reason I have not
> deployed it is [state your real reason here].

Public hosting is not a prerequisite for explaining engineering work. A
repository with architecture diagrams, migrations, executable tests, a
repeatable local setup and a recorded walkthrough can be credible evidence,
provided deployment status is described accurately.

## Why deployment is a real decision

Kafka/PostgreSQL/Redis can exceed a small free tier and free services may
sleep, lose ephemeral data, enforce quotas, or lack reliable backups.
Exposing a job endpoint can invite provider-cost abuse; a public demo also
needs strict quotas, prompt/data privacy decisions, credential isolation and
safe demo identity provisioning. A demo account is not a substitute for
authenticating every operation.

## Before responsible production exposure

- Define SLOs, supported workload and abuse limits.
- Move credentials into a managed secret store; rotate any exposed secret.
- Deploy PostgreSQL with backups, restore drills, migrations and connection
  limits; provision Kafka/managed queue with replication and retention.
- Terminate TLS; set trusted proxy/client-IP handling, CORS/origin, security
  headers and account recovery policy.
- Configure durable metrics/traces/logs, dashboards, alerts and runbooks.
- Test PostgreSQL lock races, Kafka rebalances, process termination,
  migration rollback, provider timeouts, retention/deletion and cost limits.
- Add operational controls for poison messages, permanent outbox rows and
  audited retries/replays.

Describe a public deployment only after it has been performed and its
reliability/operations evidence exists.
