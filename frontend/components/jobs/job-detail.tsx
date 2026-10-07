"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Ban,
  Check,
  CircleAlert,
  CircleX,
  Clock3,
  Database,
  FileClock,
  RefreshCw,
  Shield,
  X,
} from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { Button, ConfirmDialog, CopyButton, EmptyState, ErrorNotice, Pagination, StatusBadge } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api/client";
import { explainApiError, ApiError } from "@/lib/api/errors";
import { formatDate, safeJson } from "@/lib/format";
import { canCancel, isScheduled, isTerminal } from "@/lib/jobs/state";
import { canAccessAdmin, isDemoUser } from "@/lib/auth/access";
import type { AdminJobDetail, JobAttempt, JobDetail, JobEvent } from "@/types/api";

const HISTORY_PAGE_SIZE = 100;
const SAFE_EVENT_KEYS = new Set(["reason", "failure_category", "attempt_number", "retry_decision", "available_at", "schedule_at", "provider", "model"]);

type OperationalData =
  | {
      job: JobDetail;
      attempts: JobAttempt[];
      events: JobEvent[];
      dispatches: AdminJobDetail["dispatches"];
      isAdmin: false;
    }
  | {
      job: AdminJobDetail;
      attempts: JobAttempt[];
      events: JobEvent[];
      dispatches: AdminJobDetail["dispatches"];
      isAdmin: true;
    };

export function JobDetailClient({ jobId }: { jobId: string }) {
  const { user } = useAuth();
  const { show } = useToast();
  const admin = canAccessAdmin(user);
  const demo = isDemoUser(user);
  const [data, setData] = useState<OperationalData | null>(null);
  const dataRef = useRef<OperationalData | null>(null);
  const terminalRef = useRef(false);
  const inFlight = useRef(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [eventOffset, setEventOffset] = useState(0);
  const [attemptOffset, setAttemptOffset] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      let result: OperationalData;
      if (admin) {
        const detail = await api.admin.detail(jobId, signal);
        result = {
          job: detail,
          attempts: detail.attempts,
          events: detail.events,
          dispatches: detail.dispatches,
          isAdmin: true,
        };
      } else {
        const [detail, events, attempts] = await Promise.all([
          api.jobs.detail(jobId, signal),
          api.jobs.events(jobId, { limit: HISTORY_PAGE_SIZE, offset: eventOffset }, signal),
          api.jobs.attempts(jobId, { limit: HISTORY_PAGE_SIZE, offset: attemptOffset }, signal),
        ]);
        result = { job: detail, events, attempts, dispatches: [], isAdmin: false };
      }
      if (signal.aborted) return;
      dataRef.current = result;
      terminalRef.current = isTerminal(result.job.state);
      setData(result);
      setError(null);
    } catch (reason) {
      if (signal.aborted) return;
      setError(reason);
    } finally {
      inFlight.current = false;
      if (!signal.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [admin, attemptOffset, eventOffset, jobId]);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    let disposed = false;
    const poll = async () => {
      if (disposed || document.hidden) {
        timer = window.setTimeout(poll, 10000);
        return;
      }
      await load(controller.signal);
      if (!disposed && !terminalRef.current) timer = window.setTimeout(poll, 10000);
    };
    const onVisibility = () => {
      if (!document.hidden && !terminalRef.current && !inFlight.current) {
        if (timer) window.clearTimeout(timer);
        void poll();
      }
    };
    void poll();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      disposed = true;
      controller.abort();
      if (timer) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [load]);

  const refetch = () => {
    const controller = new AbortController();
    setRefreshing(true);
    void load(controller.signal);
  };

  async function confirmCancel() {
    if (!data || !canCancel(data.job.state)) return;
    setCancelling(true);
    try {
      let updatedState: JobDetail["state"];
      if (data.isAdmin) {
        const detail = await api.admin.cancel(jobId);
        const next: OperationalData = { job: detail, attempts: detail.attempts, events: detail.events, dispatches: detail.dispatches, isAdmin: true };
        setData(next);
        dataRef.current = next;
        updatedState = detail.state;
      } else {
        const detail = await api.jobs.cancel(jobId);
        const current = dataRef.current;
        const next: OperationalData = {
          job: detail,
          attempts: current?.attempts ?? [],
          events: current?.events ?? [],
          dispatches: [],
          isAdmin: false,
        };
        setData(next);
        dataRef.current = next;
        updatedState = detail.state;
      }
      setCancelOpen(false);
      show(
        updatedState === "CANCELLED" && acceptedScheduledJob
          ? "Scheduled job cancelled before execution."
          : "Cancellation request recorded by the API.",
        "success",
      );
      terminalRef.current = isTerminal(updatedState);
      refetch();
    } catch (reason) {
      setCancelOpen(false);
      if (reason instanceof ApiError && reason.status === 409) {
        show("The job changed before cancellation. The latest state is being refreshed.", "error");
      } else {
        show(explainApiError(reason), "error");
      }
      refetch();
    } finally {
      setCancelling(false);
    }
  }

  const eventPageHasNext = !data?.isAdmin && data?.events.length === HISTORY_PAGE_SIZE;
  const attemptPageHasNext = !data?.isAdmin && data?.attempts.length === HISTORY_PAGE_SIZE;
  const currentPageEvents = data?.events ?? [];
  const currentPageAttempts = useMemo(() => data?.attempts ?? [], [data?.attempts]);
  const record = data?.job;
  const schedule = record ? isScheduled(record.state, record.schedule_at) : false;
  const acceptedScheduledJob =
    record?.state === "ACCEPTED" && record.schedule_at !== null;
  const result = data && !data.isAdmin ? data.job.result : null;

  const safeFailureSummary = useMemo(() => {
    const latest = currentPageAttempts[currentPageAttempts.length - 1];
    if (!latest || !latest.error_class) return null;
    return `${latest.error_class}${latest.retry_decision ? ` · ${latest.retry_decision}` : ""}`;
  }, [currentPageAttempts]);

  if (loading && !data) {
    return (
      <>
        <div className="page-heading"><div><div className="eyebrow"><Activity size={14} /> Workloads / Execution</div><div className="skeleton" style={{ height: 32, width: 240, marginTop: 10 }} /><div className="skeleton skeleton-line" style={{ width: 330, marginTop: 11 }} /></div></div>
        <div className="detail-grid"><div className="detail-stack"><div className="panel skeleton-block" /><div className="panel skeleton-block" /></div><div className="panel skeleton-block" /></div>
      </>
    );
  }

  if (!data || error || !record) {
    return (
      <>
        <div className="page-heading"><div><div className="eyebrow"><Activity size={14} /> Workloads / Execution</div><h1 className="page-title">Execution detail</h1><p className="page-subtitle">The current job state could not be confirmed.</p></div></div>
        <ErrorNotice title={error instanceof ApiError && error.status === 403 ? "Access denied" : "Job detail unavailable"} message={explainApiError(error)} requestId={error instanceof ApiError ? error.requestId : null} onRetry={refetch} />
        <Link href={admin ? "/admin" : "/jobs"} className="button" style={{ marginTop: 15 }}><ArrowLeft size={14} /> Back to jobs</Link>
      </>
    );
  }

  return (
    <>
      <div className="detail-breadcrumb">
        <Link href={data.isAdmin ? "/admin" : "/jobs"}><ArrowLeft size={14} />{data.isAdmin ? "Admin jobs" : "Jobs"}</Link>
        <span aria-hidden="true">/</span>
        <span>Execution</span>
      </div>
      <div className="page-heading">
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow"><Activity size={14} /> {data.isAdmin ? "Admin / Job inspection" : "Workloads / Execution"}</div>
          <div className="detail-title-row">
            <h1 className="page-title" style={{ fontSize: 27 }}>{record.type}</h1>
            <StatusBadge state={record.state} />
            {schedule && <span className="status-badge status-accepted"><Clock3 size={12} /> FUTURE SCHEDULE</span>}
          </div>
          <div className="detail-id" style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, overflowWrap: "anywhere" }}>
            <span>{record.id}</span><CopyButton value={record.id} label="Copy job ID" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Button onClick={refetch} disabled={refreshing}><RefreshCw size={14} /> Refresh</Button>
          {!demo && canCancel(record.state) && (
            <Button variant="danger" onClick={() => setCancelOpen(true)}><X size={14} /> Cancel job</Button>
          )}
        </div>
      </div>

      <section className="panel detail-panel" style={{ marginBottom: 15 }} aria-label="Job metadata">
        <div className="detail-meta">
          <Meta label="Model" value={record.model} />
          <Meta label="Created" value={formatDate(record.created_at)} />
          <Meta label="Last updated" value={formatDate(record.updated_at)} />
          <Meta label="Schedule" value={record.schedule_at ? formatDate(record.schedule_at) : "Immediate"} />
          <Meta label="Priority / timeout" value={`${record.priority} / ${record.timeout_seconds}s`} />
          <Meta label="State version" value={`${record.version}`} mono />
          {data.isAdmin && <Meta label="Owner ID" value={record.user_id} mono />}
          {data.isAdmin && <Meta label="Execution owner" value={data.job.execution_owner ?? "Not leased"} mono />}
          {data.isAdmin && <Meta label="Lease until" value={data.job.execution_lease_until ? formatDate(data.job.execution_lease_until) : "No active lease"} />}
        </div>
      </section>

      {schedule && (
        <div className="notice warning" style={{ marginBottom: 15 }}>
          <Clock3 size={15} /><span>This job remains <code>ACCEPTED</code> until its scheduled time. Activation and dispatch are controlled by the backend scheduler and transactional outbox.</span>
        </div>
      )}
      {demo && canCancel(record.state) && (
        <div className="notice warning" style={{ marginBottom: 15 }} role="note">
          <Shield size={15} /><span>Cancellation is disabled for this read-only demo account.</span>
        </div>
      )}
      {record.state === "RETRY_SCHEDULED" && (
        <div className="notice warning" style={{ marginBottom: 15 }}>
          <RefreshCw size={15} /><span>Execution retry is scheduled by the durable backend policy. This console does not trigger or reschedule retries.</span>
        </div>
      )}
      {record.state === "FAILED" && (
        <div className="notice" style={{ marginBottom: 15 }}>
          <CircleAlert size={15} /><span>Execution reached a terminal failure state.{safeFailureSummary && <span className="mono"> Latest attempt: {safeFailureSummary}</span>}</span>
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-stack">
          <section className="panel detail-panel" aria-labelledby="timeline-title">
            <div className="detail-heading"><h2 id="timeline-title">Execution lifecycle</h2><span className="detail-heading-note">Persisted events</span></div>
            {!currentPageEvents.length ? (
              <EmptyState icon={<FileClock size={18} />} title="No lifecycle events yet" description="The backend has not returned lifecycle records for this page." />
            ) : (
              <div className="timeline">
                {currentPageEvents.map((event, index) => (
                  <TimelineEvent event={event} current={index === currentPageEvents.length - 1 && event.next_state === record.state} key={event.id} />
                ))}
              </div>
            )}
            {!data.isAdmin && (
              <Pagination
                offset={eventOffset}
                limit={HISTORY_PAGE_SIZE}
                count={currentPageEvents.length}
                hasNext={eventPageHasNext}
                onChange={setEventOffset}
              />
            )}
            {data.isAdmin && data.events.length === HISTORY_PAGE_SIZE && (
              <div className="secret-safe-note" style={{ marginTop: 13 }}>The admin detail API caps lifecycle history at 100 records.</div>
            )}
          </section>

          <section className="panel detail-panel" aria-labelledby="attempts-title">
            <div className="detail-heading"><h2 id="attempts-title">Execution attempts</h2><span className="detail-heading-note">{currentPageAttempts.length} ON THIS PAGE</span></div>
            {!currentPageAttempts.length ? (
              <EmptyState icon={<RefreshCw size={18} />} title="No attempts recorded" description="An attempt is created when a worker claims this job for execution." />
            ) : (
              currentPageAttempts.map((attempt) => <AttemptCard attempt={attempt} key={attempt.id} />)
            )}
            {!data.isAdmin && (
              <Pagination
                offset={attemptOffset}
                limit={HISTORY_PAGE_SIZE}
                count={currentPageAttempts.length}
                hasNext={attemptPageHasNext}
                onChange={setAttemptOffset}
              />
            )}
            {data.isAdmin && data.attempts.length === HISTORY_PAGE_SIZE && (
              <div className="secret-safe-note" style={{ marginTop: 13 }}>The admin detail API caps attempt history at 100 records.</div>
            )}
          </section>
        </div>

        <aside className="detail-stack">
          <section className="panel detail-panel" aria-labelledby="result-title">
            <div className="detail-heading"><h2 id="result-title">Result</h2><Database size={15} className="muted" /></div>
            {data.isAdmin ? (
              <div className="secret-safe-note">The administrative API does not return job input, configuration, or result bodies.</div>
            ) : result ? (
              <>
                <pre className="code-block">{safeJson(result.output)}</pre>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 9 }}>
                  <span className="panel-heading-note">SCHEMA {result.schema_version} · {formatDate(result.created_at)}</span>
                  <CopyButton value={safeJson(result.output)} label="Copy result JSON" />
                </div>
                {result.usage && <div className="secret-safe-note" style={{ marginTop: 11 }}><strong className="secondary">Usage metadata</strong><pre className="timeline-payload">{safeJson(result.usage, 2500)}</pre></div>}
              </>
            ) : record.state === "SUCCEEDED" ? (
              <div className="secret-safe-note">The job is succeeded, but no result body is present in the returned detail.</div>
            ) : (
              <EmptyState icon={<Database size={18} />} title="Result pending" description="A result appears only after the worker persists validated output." />
            )}
          </section>

          {!data.isAdmin && (
            <>
              <section className="panel detail-panel">
                <div className="detail-heading"><h2>Submitted input</h2><CopyButton value={safeJson(data.job.input)} label="Copy input JSON" /></div>
                <pre className="code-block">{safeJson(data.job.input)}</pre>
              </section>
              <section className="panel detail-panel">
                <div className="detail-heading"><h2>Retry policy</h2><span className="detail-heading-note">JOB CONFIGURATION</span></div>
                <pre className="code-block">{safeJson(data.job.retry_policy, 3000)}</pre>
              </section>
            </>
          )}

          {data.isAdmin && (
            <section className="panel detail-panel" aria-labelledby="dispatch-title">
              <div className="detail-heading"><h2 id="dispatch-title">Dispatch outbox</h2><Shield size={14} className="muted" /></div>
              {!data.dispatches.length ? (
                <div className="secret-safe-note">No dispatch intent is present. A future scheduled ACCEPTED job is expected to have no outbox row until due.</div>
              ) : data.dispatches.map((dispatch) => (
                <div className="dispatch-row" key={dispatch.id}>
                  <div className="dispatch-top"><span className="timeline-state">{dispatch.publication_state}</span><span className="mono muted" style={{ fontSize: 9 }}>v{dispatch.job_version}</span></div>
                  <div className="dispatch-meta"><span>{dispatch.message_type}</span><span>attempts {dispatch.attempt_count}</span>{dispatch.failure_category && <span>{dispatch.failure_category}</span>}</div>
                  <div className="dispatch-meta"><span>Created {formatDate(dispatch.created_at)}</span>{dispatch.published_at && <span>Published {formatDate(dispatch.published_at)}</span>}</div>
                  {(dispatch.available_at || dispatch.next_attempt_at) && <div className="dispatch-meta"><span>Available {formatDate(dispatch.available_at)}</span><span>Next attempt {formatDate(dispatch.next_attempt_at)}</span></div>}
                </div>
              ))}
            </section>
          )}
        </aside>
      </div>

      <ConfirmDialog
        open={cancelOpen}
        title={acceptedScheduledJob
          ? "Cancel scheduled job?"
          : "Request job cancellation?"}
        confirmLabel={acceptedScheduledJob
          ? "Cancel scheduled job"
          : "Request cancellation"}
        busy={cancelling}
        danger
        onCancel={() => setCancelOpen(false)}
        onConfirm={() => void confirmCancel()}
      >
        <p>{acceptedScheduledJob
          ? "This scheduled job has not started executing. Cancelling it now prevents worker execution:"
          : "This submits a cancellation request to the backend for:"}</p>
        <div className="mono" style={{ padding: 10, border: "1px solid var(--line)", borderRadius: 7, overflowWrap: "anywhere", color: "var(--text)" }}>{record.id}</div>
        {!acceptedScheduledJob && (
          <p>The job may still finish if a provider call is already in flight. Its state will be refreshed from the authoritative API response.</p>
        )}
      </ConfirmDialog>
    </>
  );
}

function TimelineEvent({ event, current }: { event: JobEvent; current: boolean }) {
  const Marker = event.next_state === "SUCCEEDED"
    ? Check
    : event.next_state === "FAILED" || event.next_state === "DEAD_LETTERED"
      ? CircleX
      : event.next_state === "CANCELLED" || event.next_state === "CANCEL_REQUESTED"
        ? Ban
        : event.next_state === "RUNNING"
          ? Activity
          : Clock3;
  const safePayload = Object.entries(event.payload ?? {}).filter(([key, value]) =>
    SAFE_EVENT_KEYS.has(key) && (typeof value === "string" || typeof value === "number" || typeof value === "boolean"),
  );
  return (
    <div className={`timeline-event ${current ? "current" : ""}`}>
      <span className={`timeline-marker state-${event.next_state.toLowerCase()}`} aria-label={current ? "Latest event matches current job state" : undefined}><Marker size={10} /></span>
      <div className="timeline-body">
        <div className="timeline-top">
          <span className="timeline-state">{event.next_state.replaceAll("_", " ")}</span>
          <span className="timeline-time">{formatDate(event.created_at)}</span>
        </div>
        <div className="timeline-event-name">
          {event.prior_state ? `${event.prior_state.replaceAll("_", " ")} → ` : ""}{event.event_type}
        </div>
        {safePayload.length > 0 && (
          <div className="timeline-payload">{safePayload.map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}</div>
        )}
      </div>
    </div>
  );
}

function AttemptCard({ attempt }: { attempt: JobAttempt }) {
  const duration = attempt.completed_at
    ? Math.max(0, Date.parse(attempt.completed_at) - Date.parse(attempt.started_at))
    : null;
  return (
    <div className="attempt-card">
      <div className="attempt-head">
        <span className="attempt-title">Attempt {attempt.attempt_number}</span>
        <span className={`status-badge ${attempt.error_class ? "status-failed" : "status-queued"}`}>{attempt.status.replaceAll("_", " ")}</span>
      </div>
      <div className="attempt-meta">
        {attempt.provider && <span>provider {attempt.provider}</span>}
        {attempt.model && <span>model {attempt.model}</span>}
        <span>started {formatDate(attempt.started_at)}</span>
        {duration !== null && <span>duration {(duration / 1000).toFixed(1)}s</span>}
      </div>
      {attempt.error_class && <div className="error-block">{attempt.error_class}{attempt.retry_decision ? ` · ${attempt.retry_decision}` : ""}<br />Provider error detail is intentionally not rendered in the console.</div>}
      {attempt.usage && <div className="timeline-payload">Usage: {safeJson(attempt.usage, 1200)}</div>}
    </div>
  );
}

function Meta({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><div className="meta-label">{label}</div><div className={`meta-value ${mono ? "mono" : ""}`}>{value}</div></div>;
}
