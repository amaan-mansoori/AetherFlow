"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowUpRight, CalendarClock, Filter, Plus, Search, Workflow } from "lucide-react";
import { api } from "@/lib/api/client";
import { explainApiError } from "@/lib/api/errors";
import { formatDate } from "@/lib/format";
import { isScheduled } from "@/lib/jobs/state";
import { takePendingJobSearch } from "@/lib/navigation/pending-search";
import { Button, EmptyState, ErrorNotice, Pagination, SkeletonRows, StatusBadge } from "@/components/ui/primitives";
import type { JobState, JobSummary } from "@/types/api";
import { useAuth } from "@/components/auth/auth-provider";
import { isDemoUser } from "@/lib/auth/access";

const PAGE_SIZE = 20;

export default function JobsPage() {
  const { user } = useAuth();
  const demo = isDemoUser(user);
  const [rows, setRows] = useState<JobSummary[]>([]);
  const [stateFilter, setStateFilter] = useState<JobState | "">("");
  const [scheduledOnly, setScheduledOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasNext, setHasNext] = useState(false);

  const load = useCallback(async (signal: AbortSignal) => {
    try {
      const data = await api.jobs.list({ state: stateFilter || undefined, limit: PAGE_SIZE, offset }, signal);
      if (signal.aborted) return;
      setRows(data);
      setHasNext(data.length === PAGE_SIZE);
      setError(null);
    } catch (reason) {
      if (signal.aborted) return;
      setError(explainApiError(reason));
      setRows([]);
      setHasNext(false);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, [offset, stateFilter]);

  useEffect(() => {
    const controller = new AbortController();
    // State updates occur after the API promise settles; the signal guards unmounted effects.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    const onSearch = () => {
      const pending = takePendingJobSearch();
      if (!pending) return;
      setQuery(pending);
      window.setTimeout(() => document.getElementById("job-search")?.focus(), 0);
    };
    window.addEventListener("aetherflow:job-search", onSearch);
    const pending = takePendingJobSearch();
    if (pending) {
      // Consume the command-palette handoff before Jobs mounts after client navigation.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setQuery(pending);
      window.setTimeout(() => document.getElementById("job-search")?.focus(), 0);
    }
    return () => window.removeEventListener("aetherflow:job-search", onSearch);
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows.filter((job) => {
      if (scheduledOnly && !isScheduled(job.state, job.schedule_at)) return false;
      if (!needle) return true;
      return [job.id, job.type, job.model, job.state].some((value) => value.toLowerCase().includes(needle));
    });
  }, [rows, query, scheduledOnly]);

  const refresh = () => {
    setLoading(true);
    const controller = new AbortController();
    void load(controller.signal);
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Workflow size={14} /> Workloads / Jobs</div>
          <h1 className="page-title">Jobs</h1>
          <p className="page-subtitle">Inspect durable jobs in creation order. Filters and page size follow the API contract.</p>
        </div>
        {!demo && <Link href="/submit" className="button primary"><Plus size={16} /> Submit job</Link>}
      </div>

      <section className="panel jobs-list" aria-label="Job list">
        <div className="panel-pad" style={{ paddingBottom: 13 }}>
          <div className="filter-bar">
            <label className="search-wrap">
              <Search size={15} />
              <input
                id="job-search"
                className="input"
                placeholder="Search this page by ID, type, or model"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                aria-label="Search visible jobs"
              />
            </label>
            <label className="sr-only" htmlFor="job-state-filter">Filter by state</label>
            <select
              id="job-state-filter"
              className="select filter-select"
              value={stateFilter}
              onChange={(event) => {
                setLoading(true);
                setStateFilter(event.target.value as JobState | "");
                setOffset(0);
              }}
            >
              <option value="">All states</option>
              {["ACCEPTED", "QUEUED", "RUNNING", "RETRY_SCHEDULED", "CANCEL_REQUESTED", "SUCCEEDED", "FAILED", "CANCELLED", "DEAD_LETTERED"].map((state) => (
                <option key={state} value={state}>{state.replaceAll("_", " ")}</option>
              ))}
            </select>
            <button
              className={`button small ${scheduledOnly ? "primary" : ""}`}
              aria-pressed={scheduledOnly}
              onClick={() => setScheduledOnly((value) => !value)}
              title="Filter scheduled ACCEPTED jobs on this page"
            >
              <CalendarClock size={13} /> Scheduled
            </button>
            {(query || stateFilter || scheduledOnly) && (
              <Button size="small" variant="ghost" onClick={() => {
                if (stateFilter || offset > 0) setLoading(true);
                setQuery("");
                setStateFilter("");
                setScheduledOnly(false);
                setOffset(0);
              }}>
                <Filter size={13} /> Clear filters
              </Button>
            )}
          </div>
          <div className="muted filter-explanation">
            Text search and schedule toggle apply to this API page; state is filtered server-side. The API does not expose a total count.
          </div>
        </div>

        {error && <div style={{ padding: "0 16px 14px" }}><ErrorNotice message={error} onRetry={refresh} /></div>}

        {loading ? <SkeletonRows count={5} /> : filtered.length ? (
          <JobsTable rows={filtered} />
        ) : (
          <EmptyState
            icon={<Search size={19} />}
            title={rows.length ? "No jobs match this view" : "Nothing in this page"}
            description={rows.length ? "Change or clear the current-page filters to see more results." : demo ? "No seeded example matches this view." : "This page is empty. Submit a workload or move to a previous page."}
            action={!demo && !rows.length && offset === 0 ? <Link className="button primary small" href="/submit">Submit a job</Link> : undefined}
          />
        )}
        <Pagination
          offset={offset}
          limit={PAGE_SIZE}
          count={filtered.length}
          hasNext={hasNext}
          onChange={(value) => {
            setLoading(true);
            setOffset(value);
          }}
        />
      </section>
    </>
  );
}

function JobsTable({ rows }: { rows: JobSummary[] }) {
  return (
    <div className="table-wrap mobile-cards">
      <table className="jobs-table">
        <thead><tr><th>Job</th><th>State</th><th>Created</th><th>Updated</th><th>Schedule</th><th aria-label="Open" /></tr></thead>
        <tbody>
          {rows.map((job) => (
            <tr key={job.id}>
              <td>
                <Link className="table-link job-ref" href={`/jobs/${encodeURIComponent(job.id)}`}>
                  <span className="job-ref-mark"><Activity size={13} /></span>
                  <span>
                    <span className="job-name">{job.type}</span>
                    <span className="job-sub">{job.id.slice(0, 8)} · {job.model}</span>
                  </span>
                </Link>
              </td>
              <td><StatusBadge state={job.state} /></td>
              <td data-label="Created" data-hide-mobile><span className="mono muted" style={{ fontSize: 11 }}>{formatDate(job.created_at)}</span></td>
              <td data-label="Updated"><span className="mono muted" style={{ fontSize: 11 }}>{formatDate(job.updated_at)}</span></td>
              <td data-label="Schedule">
                {job.schedule_at ? <span className="mono secondary" style={{ fontSize: 11 }}>{formatDate(job.schedule_at)}</span> : <span className="muted" style={{ fontSize: 12 }}>Immediate</span>}
              </td>
              <td data-action><Link href={`/jobs/${encodeURIComponent(job.id)}`} className="icon-button" aria-label={`Open job ${job.id}`}><ArrowUpRight size={14} /></Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
