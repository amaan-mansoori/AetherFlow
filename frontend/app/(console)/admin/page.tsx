"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { ArrowUpRight, CalendarClock, Shield, Workflow } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { Button, EmptyState, ErrorNotice, Pagination, SkeletonRows, StatusBadge } from "@/components/ui/primitives";
import { api } from "@/lib/api/client";
import { explainApiError } from "@/lib/api/errors";
import { formatDate } from "@/lib/format";
import { canAccessAdmin } from "@/lib/auth/access";
import type { JobState, JobSummary } from "@/types/api";

const PAGE_SIZE = 25;
interface DraftFilters {
  job_id: string;
  user_id: string;
  state: JobState | "";
  model: string;
  provider: string;
  created_from: string;
  created_to: string;
  schedule_from: string;
  schedule_to: string;
  priority: string;
}
const emptyFilters: DraftFilters = {
  job_id: "", user_id: "", state: "", model: "", provider: "",
  created_from: "", created_to: "", schedule_from: "", schedule_to: "", priority: "",
};

function toApiFilters(draft: DraftFilters) {
  const toIso = (value: string) => value ? new Date(value).toISOString() : undefined;
  return {
    job_id: draft.job_id || undefined,
    user_id: draft.user_id || undefined,
    state: draft.state || undefined,
    model: draft.model || undefined,
    provider: draft.provider || undefined,
    created_from: toIso(draft.created_from),
    created_to: toIso(draft.created_to),
    schedule_from: toIso(draft.schedule_from),
    schedule_to: toIso(draft.schedule_to),
    priority: draft.priority === "" ? undefined : Number(draft.priority),
    limit: PAGE_SIZE,
  };
}

export default function AdminPage() {
  const { user } = useAuth();
  const [draft, setDraft] = useState<DraftFilters>(emptyFilters);
  const [filters, setFilters] = useState(toApiFilters(emptyFilters));
  const [rows, setRows] = useState<JobSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasNext, setHasNext] = useState(false);

  const load = useCallback(async (signal: AbortSignal) => {
    try {
      const result = await api.admin.list({ ...filters, offset }, signal);
      if (signal.aborted) return;
      setRows(result);
      setHasNext(result.length === PAGE_SIZE);
      setError(null);
    } catch (reason) {
      if (signal.aborted) return;
      setRows([]);
      setError(explainApiError(reason));
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    if (!canAccessAdmin(user)) return;
    const controller = new AbortController();
    // State updates occur after the API promise settles; the signal guards unmounted effects.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(controller.signal);
    return () => controller.abort();
  }, [load, user]);

  if (!canAccessAdmin(user)) {
    return (
      <>
        <div className="page-heading"><div><div className="eyebrow"><Shield size={14} /> Restricted area</div><h1 className="page-title">Admin operations</h1><p className="page-subtitle">This surface requires the ADMIN role.</p></div></div>
        <div className="panel"><EmptyState icon={<Shield size={20} />} title="No admin access" description="Your account does not have the ADMIN role. The server enforces this boundary independently of this interface." /></div>
      </>
    );
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setOffset(0);
    setFilters(toApiFilters(draft));
  }

  const refresh = () => {
    setLoading(true);
    const controller = new AbortController();
    void load(controller.signal);
  };

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><Shield size={14} /> Admin / Operations</div>
          <h1 className="page-title">Job inspection</h1>
          <p className="page-subtitle">Read durable operational records across accounts. Mutations remain narrow and server-authorized.</p>
        </div>
      </div>
      {error && <ErrorNotice title="Admin request rejected" message={error} onRetry={refresh} />}
      <section className="panel admin-jobs-panel">
        <form onSubmit={applyFilters} className="panel-pad admin-filter-form">
          <div className="section-header" style={{ margin: "0 0 14px" }}>
            <div><h2 className="section-title">Filters</h2><span className="panel-heading-note">Up to 25 jobs per page · newest first</span></div>
            <Button type="submit" variant="primary" size="small" disabled={loading}><Workflow size={13} /> Apply filters</Button>
          </div>
          <div className="advanced-filters">
            <Field label="Job ID"><input className="input" value={draft.job_id} onChange={(event) => setDraft({ ...draft, job_id: event.target.value.trim() })} /></Field>
            <Field label="User ID"><input className="input" value={draft.user_id} onChange={(event) => setDraft({ ...draft, user_id: event.target.value.trim() })} /></Field>
            <Field label="State">
              <select className="select" value={draft.state} onChange={(event) => setDraft({ ...draft, state: event.target.value as JobState | "" })}>
                <option value="">All states</option>
                {["ACCEPTED", "QUEUED", "RUNNING", "RETRY_SCHEDULED", "CANCEL_REQUESTED", "SUCCEEDED", "FAILED", "CANCELLED", "DEAD_LETTERED"].map((state) => <option key={state} value={state}>{state.replaceAll("_", " ")}</option>)}
              </select>
            </Field>
            <Field label="Model"><input className="input" maxLength={64} value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} /></Field>
            <Field label="Provider"><input className="input" maxLength={64} value={draft.provider} onChange={(event) => setDraft({ ...draft, provider: event.target.value })} /></Field>
            <Field label="Priority"><select className="select" value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })}><option value="">Any</option>{Array.from({ length: 11 }, (_, index) => <option key={index} value={index}>{index}</option>)}</select></Field>
            <Field label="Created after"><input className="input" type="datetime-local" value={draft.created_from} onChange={(event) => setDraft({ ...draft, created_from: event.target.value })} /></Field>
            <Field label="Created before"><input className="input" type="datetime-local" value={draft.created_to} onChange={(event) => setDraft({ ...draft, created_to: event.target.value })} /></Field>
            <Field label="Scheduled after"><input className="input" type="datetime-local" value={draft.schedule_from} onChange={(event) => setDraft({ ...draft, schedule_from: event.target.value })} /></Field>
            <Field label="Scheduled before"><input className="input" type="datetime-local" value={draft.schedule_to} onChange={(event) => setDraft({ ...draft, schedule_to: event.target.value })} /></Field>
          </div>
          <div className="muted" style={{ marginTop: 10, fontSize: 10 }}><CalendarClock size={12} style={{ verticalAlign: "middle", marginRight: 5 }} />Dates are sent as timezone-aware ISO timestamps; no arbitrary ordering or SQL filters are accepted.</div>
        </form>
        {loading ? <SkeletonRows count={5} /> : rows.length ? (
          <div className="table-wrap mobile-cards">
            <table className="jobs-table">
              <thead><tr><th>Job</th><th>State</th><th>Owner</th><th>Created</th><th>Schedule</th><th /></tr></thead>
              <tbody>{rows.map((job) => (
                <tr key={job.id}>
                  <td><Link href={`/jobs/${encodeURIComponent(job.id)}`} className="table-link job-ref"><span className="job-ref-mark"><Workflow size={13} /></span><span><span className="job-name">{job.type}</span><span className="job-sub">{job.id.slice(0, 8)} · {job.model}</span></span></Link></td>
                  <td><StatusBadge state={job.state} /></td>
                  <td data-label="Owner"><span className="mono muted" style={{ fontSize: 11 }}>{job.user_id.slice(0, 8)}</span></td>
                  <td data-label="Created"><span className="mono muted" style={{ fontSize: 11 }}>{formatDate(job.created_at)}</span></td>
                  <td data-label="Schedule">{job.schedule_at ? <span className="mono secondary" style={{ fontSize: 11 }}>{formatDate(job.schedule_at)}</span> : <span className="muted" style={{ fontSize: 12 }}>Immediate</span>}</td>
                  <td data-action><Link href={`/jobs/${encodeURIComponent(job.id)}`} className="icon-button" aria-label={`Inspect ${job.id}`}><ArrowUpRight size={14} /></Link></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon={<Workflow size={20} />} title="No matching jobs" description="Try a wider time range or clear one of the filters." />
        )}
        <Pagination offset={offset} limit={PAGE_SIZE} count={rows.length} hasNext={hasNext} onChange={(value) => {
          setLoading(true);
          setOffset(value);
        }} />
      </section>
    </>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="filter-field"><span>{label}</span>{children}</label>;
}
