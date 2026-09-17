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
