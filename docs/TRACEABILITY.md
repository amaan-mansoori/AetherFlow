# Requirement Traceability

**Status:** Architecture / Specification Phase  
**Format:** Requirement -> Component -> API -> Database -> Test -> Documentation

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Authentication | API/auth | `/auth/*` | users, roles, user_roles | auth integration/API | API, SECURITY, TESTING |
| API keys | API/auth | `/api-keys` | api_keys | key lifecycle/security | API, SECURITY |
| Job submission | API/domain/Kafka | `POST /jobs` | jobs, idempotency_records | API/integration/concurrency | PRD, DATA-FLOW, DATABASE |
| Idempotency | Domain/database | `POST /jobs` + header | idempotency_records | concurrent duplicate/mismatch | ARCHITECTURE, DATABASE, FAILURE-MATRIX |
| State machine | Domain/worker | job actions | jobs, job_events | transition unit/API | RELIABILITY, API |
| Worker execution | Worker/Kafka/provider | job detail | jobs, job_attempts, job_results | worker integration/failure | DATA-FLOW, FAILURE-MATRIX |
| Retry/dead letter | Worker/scheduler | retry action | attempts/events/jobs | provider failure matrix | RELIABILITY, FAILURE-MATRIX |
| Cancellation | Domain/worker/provider | cancel endpoint | jobs, events, attempts | before/during execution | API, FAILURE-MATRIX |
| Rate limiting/cache | Redis/API | all protected routes | none authoritative | Redis integration/degraded mode | ARCHITECTURE, SCALING |
| Observability | All processes | metrics/health/admin | optional event metadata | telemetry smoke tests | OBSERVABILITY |
| Console | Next.js/API | read/action APIs | read models/entities | E2E/accessibility | UI-UX, DESIGN-SYSTEM |
| Deployment | Containers/Kubernetes | health endpoints | migrations | build/smoke/deploy | DEPLOYMENT, CI-CD |
| Performance evidence | Benchmark harness | measured API/workflow | telemetry | load/performance | PERFORMANCE, EVALUATION |

## Phase 1 implementation mapping

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Foundation startup/configuration | `backend/src/aetherflow/main.py`, config | `/health/live` | none | `backend/tests/test_app.py`, `test_config.py` | README, DEPLOYMENT |
| Database readiness | async SQLAlchemy session infrastructure | `/health/ready` | PostgreSQL connection | `backend/tests/test_app.py`, `test_database.py`; PostgreSQL integration check | DATABASE, RELIABILITY |
| Request IDs/log context | request middleware and observability context | response `X-Request-ID` | none | `backend/tests/test_app.py` | OBSERVABILITY, SECURITY |
| Error contract | centralized API handlers | all current HTTP errors | none | `backend/tests/test_app.py` | API-ERRORS |

## Phase 2 implementation mapping

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Registration/password security | `auth/service.py`, `auth/passwords.py` | `POST /api/v1/auth/register` | users, roles, user_roles | `test_auth.py` | API, SECURITY |
| Login/access authentication | `auth/tokens.py`, `auth/policies.py` | `POST /api/v1/auth/login`, `GET /auth/me` | users, audit_logs | `test_auth.py` | API, SECURITY |
| Refresh/logout | `auth/service.py`, cookie routes | `POST /auth/refresh`, `POST /auth/logout` | refresh_sessions, audit_logs | `test_auth.py` | API, SECURITY, THREAT-MODEL |
| RBAC | `auth/policies.py` | reusable dependencies | roles, user_roles, audit_logs | `test_auth.py` | API, SECURITY |
| API keys | `auth/tokens.py`, `auth/service.py`, key routes | `/api/v1/api-keys` | api_keys, audit_logs | `test_auth.py` | API, DATABASE, SECURITY |
| Security audit | `auth/service.py`, policies | security actions | audit_logs | identity audit assertions | SECURITY, DATABASE |
| Identity migration | Alembic revision | N/A | all Phase 2 identity tables | migration upgrade/downgrade | DATABASE, DEPLOYMENT |

This matrix is intentionally a phase-0 contract. Test file names and concrete component symbols will be added when implementation begins.

## Phase 3 implementation mapping

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Durable job submission | `jobs/service.py`, job routes | `POST /api/v1/jobs` | `jobs`, `job_events` | `test_jobs.py` | API, DATABASE |
| Idempotency | `jobs/idempotency.py`, `jobs/service.py` | `POST /api/v1/jobs` + `Idempotency-Key` | `idempotency_records` | replay, mismatch, principal-scope tests; concurrent PostgreSQL verification pending | ARCHITECTURE, DATABASE |
| State machine and CAS | `jobs/state_machine.py`, `jobs/service.py` | lifecycle actions | `jobs`, `job_events` | legal/illegal/stale-version tests | RELIABILITY, DATABASE |
| Ownership and cancellation | job routes and services | job read/events/attempts/cancel routes | `jobs`, `job_events` | ownership/admin/cancellation tests | API, SECURITY |
| Attempts and results | `jobs/service.py` | job detail subresources | `job_attempts`, `job_results` | uniqueness and eligibility tests | DATABASE, TESTING |

## Phase 4A implementation mapping

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Execution contract | `jobs/execution.py` | none | existing jobs/results | `test_phase4a.py` | ARCHITECTURE, RELIABILITY |
| Worker lifecycle | `jobs/worker.py`, existing job services | none | existing jobs, attempts, results, events | success/failure/cancellation/stale-message tests | ARCHITECTURE, RELIABILITY |
| Dispatch boundary | `jobs/dispatch.py` | future broker boundary | none | local round-trip/dispatch failure tests | ARCHITECTURE, KNOWN-LIMITATIONS |

Retry execution, Redis, provider integration, admin operations, frontend, and
deployment remain future-phase requirements.

## Phase 4B implementation mapping

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Kafka envelope and producer | `infrastructure/kafka.py`, settings | outbox publisher runtime | existing jobs/outbox | `test_kafka.py` serialization/key/failure tests | ARCHITECTURE, RELIABILITY |
| Kafka consumer and acknowledgement | `infrastructure/kafka.py`, `jobs/worker.py` | none | existing jobs/events | receive/ack and Phase 4A worker tests | ARCHITECTURE, TESTING |
| Duplicate delivery safety | existing worker CAS/state rules | none | jobs version/state | duplicate/stale/terminal tests | RELIABILITY, KNOWN-LIMITATIONS |

Redis, provider integration, admin operations, frontend, and deployment remain
future-phase requirements.

## Phase 4C implementation mapping

| Requirement | Component | API | Database | Test | Documentation |
|---|---|---|---|---|---|
| Atomic dispatch intent | `jobs/service.py` | `POST /api/v1/jobs` | `outbox_dispatches` | `test_outbox.py` atomicity/replay tests | ARCHITECTURE, DATABASE |
| Outbox publication/recovery | `jobs/outbox.py`, Kafka dispatcher | internal runtime only | outbox publication metadata | publication success/failure/recovery tests | RELIABILITY, TESTING |
| Duplicate publication safety | existing Worker/CAS | none | jobs and outbox | duplicate dispatch tests | RELIABILITY, KNOWN-LIMITATIONS |

Redis, general scheduling, external providers, admin operations,
frontend, and deployment remain future-phase requirements.

## Phase 4D/4E/4F implementation mapping

| Requirement | Component | Database | Test | Documentation |
|---|---|---|---|---|
| Independent bounded publisher | `runtime/outbox_publisher.py`, `jobs/outbox_runtime.py` | outbox claims/leases | runtime lifecycle tests | ARCHITECTURE, RELIABILITY |
| Bounded dispatch retry | `jobs/retry.py`, `jobs/outbox.py` | retry metadata and eligibility index | backoff/terminal tests | DATABASE, RELIABILITY |
| Worker crash recovery | `jobs/worker.py` | execution owner/lease | expired lease recovery test | ARCHITECTURE, RELIABILITY |

PostgreSQL concurrency and Kafka runtime integration remain environment-gated
verification rather than claims made by SQLite/fake-client tests.

## Phase 5 implementation mapping

| Requirement | Component | Database | Test | Documentation |
|---|---|---|---|---|
| Provider boundary and registry | `jobs/providers.py`, `jobs/execution.py` | existing job configuration | `test_phase5_providers.py` registry tests | ARCHITECTURE, API |
| Deterministic local provider | `MockProviderAdapter` | existing results/attempts | mock success/failure tests | ADR-0008, TESTING |
| Provider failure/output normalization | `ExecutionFailureKind`, `ProviderExecutor` | existing attempt error/provider fields | category, malformed-output, and worker persistence tests | RELIABILITY, DATABASE |
| Execution timeout | `jobs/worker.py` | existing attempt/state/lease fields | timeout durability test | RELIABILITY, DATA-FLOW |
| Provider credential protection | `JobCreateRequest`, runtime settings | no credential columns | schema rejection test | SECURITY, API |

External provider transport remains deferred; real PostgreSQL, Kafka, and
external-provider verification are environment-gated.

## Phase 6 implementation mapping

| Requirement | Component | Database | Test | Documentation |
|---|---|---|---|---|
| Centralized execution failure policy | `jobs/retry.py` | persisted job retry policy | policy classification/backoff tests | RELIABILITY, ADR-0015 |
| Atomic retry scheduling | `jobs/service.py`, `jobs/worker.py` | attempt metadata, job state/version, retry outbox intent | retry persistence and exhaustion tests | DATABASE, DATA-FLOW |
| Future retry dispatch | `jobs/outbox.py` | `available_at`, `(job_id, job_version)` uniqueness | eligibility and duplicate publication tests | ARCHITECTURE, RELIABILITY |
| Cancellation/stale safety | state machine, outbox claim, worker CAS | versioned state and intent | cancellation, duplicate, stale tests | RELIABILITY, KNOWN-LIMITATIONS |

Execution retries are locally verified with SQLite/local dispatch. PostgreSQL
and Kafka integration/concurrency remain environment-gated.
