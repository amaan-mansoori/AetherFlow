"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowRight, Plus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api/client";
import { explainApiError } from "@/lib/api/errors";
import { formatDate } from "@/lib/format";
import { isScheduled, isTerminal } from "@/lib/jobs/state";
import { Button, EmptyState, ErrorNotice, StatusBadge } from "@/components/ui/primitives";
import type { HealthResponse, JobSummary } from "@/types/api";
import { useAuth } from "@/components/auth/auth-provider";
import { isDemoUser } from "@/lib/auth/access";

interface Snapshot {
  jobs: JobSummary[];
  live: HealthResponse | null;
  ready: HealthResponse | null;
  liveError: string | null;
  readyError: string | null;
}

const initial: Snapshot = {
  jobs: [],
  live: null,
  ready: null,
  liveError: null,
  readyError: null,
};

export default function OverviewPage() {
  const { user } = useAuth();
  const demo = isDemoUser(user);
  const [snapshot, setSnapshot] = useState<Snapshot>(initial);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const inFlight = useRef(false);

  const load = useCallback(async (signal: AbortSignal) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setRefreshing(true);
    try {
      const [jobsResult, liveResult, readyResult] = await Promise.allSettled([
        api.jobs.list({ limit: 100, offset: 0 }, signal),
        api.health.live(signal),
        api.health.ready(signal),
      ]);
      if (signal.aborted) return;
      if (jobsResult.status === "rejected") {
        setError(explainApiError(jobsResult.reason));
      } else {
        setError(null);
        setSnapshot({
          jobs: jobsResult.value,
          live: liveResult.status === "fulfilled" ? liveResult.value : null,
          ready: readyResult.status === "fulfilled" ? readyResult.value : null,
          liveError: liveResult.status === "rejected" ? explainApiError(liveResult.reason) : null,
          readyError: readyResult.status === "rejected" ? explainApiError(readyResult.reason) : null,
        });
        setLastUpdated(new Date());
      }
    } finally {
      inFlight.current = false;
      if (!signal.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const timer = window.setInterval(() => {
      if (!document.hidden) void load(controller.signal);
    }, 20000);
    const onVisibility = () => {
      if (!document.hidden) void load(controller.signal);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [load]);

  const counts = useMemo(() => {
    const jobs = snapshot.jobs;
    return {
      total: jobs.length,
      nonTerminal: jobs.filter((job) => !isTerminal(job.state)).length,
      attention: jobs.filter((job) => job.state === "FAILED" || job.state === "DEAD_LETTERED").length,
      scheduled: jobs.filter((job) => isScheduled(job.state, job.schedule_at)).length,
    };
  }, [snapshot.jobs]);

  const latest = useMemo(
    () => [...snapshot.jobs].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)),
    [snapshot.jobs],
  );

  const distribution = useMemo(() => {
    const states = new Map<JobSummary["state"], number>();
    for (const job of snapshot.jobs) states.set(job.state, (states.get(job.state) ?? 0) + 1);
    return [...states.entries()].sort((a, b) => b[1] - a[1]);
  }, [snapshot.jobs]);

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Activity size={14} /> Operations / Overview</div>
          <h1 className="page-title">Overview</h1>
          <p className="page-subtitle">Recent jobs and API signals for your account.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={() => {
            const controller = new AbortController();
            void load(controller.signal);
          }} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? "status-pulse" : ""} /> Refresh
          </Button>
          {!demo && <Link href="/submit" className="button primary"><Plus size={16} /> Submit job</Link>}
        </div>
      </div>

      {error && <ErrorNotice title="Job snapshot unavailable" message={error} onRetry={() => {
        const controller = new AbortController();
        void load(controller.signal);
      }} />}

      {lastUpdated ? (
        <>
          <div className="metric-grid" aria-label="Job sample summary">
            <Metric label="Needs attention" value={counts.attention} note="Failed or dead-lettered" emphasis={counts.attention > 0} />
            <Metric label="Non-terminal" value={counts.nonTerminal} note="Not in a terminal state" />
            <Metric label="Scheduled" value={counts.scheduled} note="Future jobs in this sample" />
            <Metric label="Recent jobs" value={counts.total} note="Up to 100 visible records" />
          </div>
          <div className="snapshot-strip" role="status">
            <span>{error ? "Showing the last successful sample; refresh failed." : "Counts cover up to 100 recent jobs visible to your account, not account-wide totals."}</span>
            <span>Last updated {formatDate(lastUpdated.toISOString())}</span>
          </div>
        </>
      ) : loading ? (
        <div className="metric-grid" aria-label="Loading job summary" aria-busy="true">
          {["Needs attention", "Non-terminal", "Scheduled", "Recent jobs"].map((label) => (
            <div className="metric" key={label}>
              <div className="metric-top">{label}</div>
              <div className="skeleton" style={{ width: 54, height: 30, marginTop: 10 }} />
              <div className="skeleton" style={{ width: "75%", height: 12, marginTop: 8 }} />
            </div>
          ))}
        </div>
      ) : null}

      <div className="dashboard-grid">
        <section className="panel dashboard-recent" aria-labelledby="recent-jobs-title">
          <div className="panel-heading">
            <div>
              <h2 className="panel-heading-title" id="recent-jobs-title">Recent jobs</h2>
              <span className="panel-heading-note">Ordered by last update</span>
            </div>
            <Link href="/jobs" className="button ghost small">All jobs <ArrowRight size={13} /></Link>
          </div>
          {loading ? (
            <div aria-busy="true" style={{ padding: "12px 16px" }}>
              {[0, 1, 2, 3].map((item) => <div className="skeleton skeleton-row" key={item} />)}
            </div>
          ) : !latest.length ? (
            <EmptyState icon={<Activity size={20} />} title="No jobs yet" description={demo ? "No seeded records are available for this demo account." : "Submit a job to begin tracking its persisted execution history."} action={!demo ? <Link className="button primary small" href="/submit">Create a job</Link> : undefined} />
          ) : (
            <JobRows jobs={latest.slice(0, 6)} />
          )}
        </section>

        <aside className="service-panel" aria-label="System and sample state">
          <div className="section-label">Service signals</div>
          <div style={{ marginTop: 9 }}>
            <HealthRow label="API liveness" detail={snapshot.liveError ?? (snapshot.live ? "Process response" : "Liveness check")} ok={snapshot.live ? snapshot.live.status === "alive" : null} />
            <HealthRow label="API readiness" detail={snapshot.readyError ?? (snapshot.ready?.database ? "Database check" : snapshot.ready ? "Dependency check" : "Readiness check")} ok={snapshot.ready ? snapshot.ready.status === "ready" : null} />
          </div>
          <div className="section-header" style={{ marginTop: 26 }}>
            <div>
              <h2 className="section-title">State mix</h2>
              <span className="panel-heading-note">Recent sample</span>
            </div>
          </div>
          {!distribution.length ? (
            <div className="muted" style={{ padding: "14px 0", fontSize: 11 }}>State distribution appears after the first job is submitted.</div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {distribution.map(([state, count]) => (
                <div key={state}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 5 }}>
                    <StatusBadge state={state} />
                    <span className="mono muted" style={{ fontSize: 10 }}>{count}</span>
                  </div>
                  <div style={{ height: 3, borderRadius: 4, background: "rgba(255,255,255,.05)" }}>
                    <div style={{ height: 3, width: `${Math.max(4, (count / Math.max(counts.total, 1)) * 100)}%`, borderRadius: 4, background: "var(--accent)" }} />
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="secret-safe-note" style={{ marginTop: 21 }}>
            {snapshot.ready?.status === "ready"
              ? "The API reports database readiness. Worker and broker health are not exposed by the current API."
              : "Readiness could not be confirmed. This view does not infer worker or broker health."}
          </div>
        </aside>
      </div>
    </>
  );
}

function Metric({ label, value, note, emphasis = false }: { label: string; value: number; note: string; emphasis?: boolean }) {
  return (
    <div className={`metric ${emphasis ? "metric-attention" : ""}`}>
      <div className="metric-top"><span>{label}</span></div>
      <div className="metric-value" aria-live="polite">{value}</div>
      <div className="metric-note">{note}</div>
    </div>
  );
}

function HealthRow({ label, detail, ok }: { label: string; detail: string; ok: boolean | null }) {
  return (
    <div className="health-row">
      <span className={`health-dot ${ok === null ? "unknown" : ok ? "" : "down"}`} aria-hidden="true" />
      <span className="health-title"><strong style={{ display: "block", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>{label}</strong><span className="muted" style={{ fontSize: 11 }}>{detail}</span></span>
      <span className={`health-value ${ok === null ? "unknown" : ok ? "" : "down"}`}>{ok === null ? "Unknown" : ok ? "Healthy" : "Unavailable"}</span>
    </div>
  );
}

function JobRows({ jobs }: { jobs: JobSummary[] }) {
  return (
    <div className="table-wrap mobile-cards">
      <table className="jobs-table">
        <thead><tr><th>Job</th><th>State</th><th>Updated</th></tr></thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>
                <Link href={`/jobs/${encodeURIComponent(job.id)}`} className="table-link job-ref">
                  <span className="job-ref-mark"><Activity size={13} /></span>
                  <span><span className="job-name">{job.type}</span><span className="job-sub">{job.id.slice(0, 8)} · {job.model}</span></span>
                </Link>
              </td>
              <td><StatusBadge state={job.state} /></td>
              <td data-label="Updated"><span className="mono muted" style={{ fontSize: 11 }}>{formatDate(job.updated_at)}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
