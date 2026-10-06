"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Activity, ArrowUpRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api/client";
import { explainApiError } from "@/lib/api/errors";
import { formatDate } from "@/lib/format";
import { Button, EmptyState, ErrorNotice, StatusBadge } from "@/components/ui/primitives";
import type { JobSummary } from "@/types/api";

export default function ActivityPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async (signal: AbortSignal) => {
    try {
      const result = await api.jobs.list({ limit: 50, offset: 0 }, signal);
      if (signal.aborted) return;
      setJobs(result);
      setError(null);
    } catch (reason) {
      if (signal.aborted) return;
      setError(explainApiError(reason));
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    // State updates occur after the API promise settles; the signal guards unmounted effects.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);
  const refresh = () => {
    setLoading(true);
    const controller = new AbortController();
    void load(controller.signal);
  };

  const ordered = [...jobs].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Activity size={14} /> Execution / Activity</div>
          <h1 className="page-title">Activity</h1>
          <p className="page-subtitle">The newest job records visible to your account, ordered by last update. Full lifecycle history is available in each execution detail.</p>
        </div>
        <Button onClick={refresh} disabled={loading}><RefreshCw size={14} /> Refresh</Button>
      </div>
      {error && <ErrorNotice message={error} onRetry={refresh} />}
      <section className="panel activity-list" aria-label="Recent job updates" style={{ marginTop: 18 }}>
        <div className="panel-heading"><div><h2 className="panel-heading-title">Recently updated jobs</h2><span className="panel-heading-note">Newest 50 records returned by the jobs API</span></div><span className="panel-heading-note">Not a global event feed</span></div>
        {loading ? (
          <div aria-busy="true">{[0, 1, 2, 3, 4].map((index) => <div className="skeleton-row" key={index} />)}</div>
        ) : !ordered.length ? (
          <EmptyState icon={<Activity size={19} />} title="No activity to show" description="Updated job records will appear here after you submit a workload." />
        ) : (
          <div style={{ padding: "5px 18px" }}>
            {ordered.map((job) => (
              <Link className="timeline-event" href={`/jobs/${encodeURIComponent(job.id)}`} key={job.id} style={{ display: "grid", paddingTop: 15, borderBottom: "1px solid var(--line)" }}>
                <span className="timeline-marker"><Activity size={9} /></span>
                <span className="timeline-body">
                  <span className="timeline-top"><span className="timeline-state">{job.type} <span className="muted">· {job.model}</span></span><span className="timeline-time">{formatDate(job.updated_at)}</span></span>
                  <span style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", marginTop: 7 }}>
                    <span className="mono muted activity-id">{job.id}</span><StatusBadge state={job.state} /><ArrowUpRight size={13} className="muted" />
                  </span>
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
