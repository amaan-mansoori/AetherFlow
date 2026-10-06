"use client";

import Link from "next/link";
import { useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, Check, ChevronDown, CircleAlert, Clock3, FilePlus2, KeyRound, Workflow } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { api } from "@/lib/api/client";
import { explainApiError } from "@/lib/api/errors";
import { buildSubmission } from "@/lib/jobs/submission";
import { formatDate } from "@/lib/format";
import type { JobDetail } from "@/types/api";
import type { JobSubmission } from "@/types/api";
import { useAuth } from "@/components/auth/auth-provider";
import { isDemoUser } from "@/lib/auth/access";

export default function SubmitPage() {
  const { user } = useAuth();
  const demo = isDemoUser(user);
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("");
  const [configuration, setConfiguration] = useState("{}");
  const [metadata, setMetadata] = useState("{}");
  const [priority, setPriority] = useState(0);
  const [timeout, setTimeout] = useState(300);
  const [maxAttempts, setMaxAttempts] = useState(3);
  const [initialBackoff, setInitialBackoff] = useState(1);
  const [maxBackoff, setMaxBackoff] = useState(60);
  const [multiplier, setMultiplier] = useState(2);
  const [scheduleAt, setScheduleAt] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [idempotency, setIdempotency] = useState<{ fingerprint: string; key: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<JobDetail | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    let payload: JobSubmission;
    try {
      payload = buildSubmission({
        model,
        prompt,
        configuration,
        metadata,
        priority,
        timeout,
        maxAttempts,
        initialBackoff,
        maxBackoff,
        multiplier,
        scheduleAt,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Review the job fields.");
      return;
    }
    setSubmitting(true);
    try {
      const fingerprint = JSON.stringify(payload);
      const key =
        idempotency?.fingerprint === fingerprint ? idempotency.key : crypto.randomUUID();
      setIdempotency({ fingerprint, key });
      const result = await api.jobs.create(payload, key);
      setCreated(result);
    } catch (reason) {
      setError(explainApiError(reason));
    } finally {
      setSubmitting(false);
    }
  }

  if (created) {
    return (
      <>
        <div className="page-heading"><div><div className="eyebrow"><FilePlus2 size={14} /> Workloads / Submit</div><h1 className="page-title">Job accepted</h1><p className="page-subtitle">The API returned the durable job record. Execution state will update only when observed from the backend.</p></div></div>
        <section className="success-callout" aria-live="polite">
          <div className="success-title"><span className="brand-mark" style={{ width: 28, height: 28, flexBasis: 28, borderRadius: 8 }}><Check size={15} /></span>Job persisted</div>
          <div className="detail-meta">
            <Meta label="Job ID" value={created.id} mono />
            <Meta label="Initial state" value={created.state.replaceAll("_", " ")} />
            <Meta label="Model" value={created.model} />
            <Meta label="Schedule" value={created.schedule_at ? formatDate(created.schedule_at) : "Immediate"} />
          </div>
          <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
            <Link className="button primary" href={`/jobs/${encodeURIComponent(created.id)}`}>Open execution <ArrowRight size={14} /></Link>
            <Link className="button" href="/jobs">Back to jobs</Link>
          </div>
          <div className="idempotency-note">The API returned the durable record for this idempotent submission.</div>
        </section>
      </>
    );
  }

  if (demo) {
    return (
      <>
        <div className="page-heading">
          <div><div className="eyebrow"><FilePlus2 size={14} /> Demo workspace</div><h1 className="page-title">Read-only access</h1><p className="page-subtitle">Job submission is disabled for the recruiter demo account.</p></div>
        </div>
        <div className="notice warning" role="note">
          <KeyRound size={15} /><span>This account can inspect its seeded, clearly labelled job fixtures. It cannot dispatch work, create API keys, or access administrative operations.</span>
        </div>
        <Link href="/jobs" className="button" style={{ marginTop: 16 }}>Return to demo jobs</Link>
      </>
    );
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><FilePlus2 size={14} /> Workloads / Submit</div>
          <h1 className="page-title">Submit job</h1>
          <p className="page-subtitle">Create structured inference work that is persisted before asynchronous dispatch.</p>
        </div>
        <span className="status-badge status-queued"><KeyRound size={13} /> Idempotent request</span>
      </div>

      <form onSubmit={submit} className="form-layout">
        <section className="panel form-panel" aria-label="Job request fields">
          <div className="eyebrow"><Workflow size={14} /> Structured inference</div>
          <div className="form-group">
            <label className="form-label" htmlFor="model">Model identifier</label>
            <input id="model" className="input" required maxLength={64} value={model} onChange={(event) => setModel(event.target.value)} placeholder="For example: configured model name" />
            <span className="form-help">The runtime-selected provider interprets this identifier. Provider credentials are configured server-side.</span>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="prompt">Prompt</label>
            <textarea id="prompt" className="textarea" required maxLength={20000} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the structured inference task…" style={{ minHeight: 175 }} />
            <span className="form-help">The current workload type requires a non-empty string at <code>input.prompt</code>.</span>
          </div>

          <button type="button" className="details-toggle" aria-expanded={advanced} onClick={() => setAdvanced((value) => !value)}>
            <ChevronDown size={14} style={{ transform: advanced ? "rotate(180deg)" : undefined, transition: "transform .16s" }} />
            {advanced ? "Hide advanced settings" : "Advanced settings"}
          </button>
          {advanced && (
            <div>
              <div className="form-grid">
                <Field label="Priority (0–10)" htmlFor="priority"><input id="priority" className="input" type="number" min={0} max={10} value={priority} onChange={(event) => setPriority(Number(event.target.value))} /></Field>
                <Field label="Timeout seconds (5–3600)" htmlFor="timeout"><input id="timeout" className="input" type="number" min={5} max={3600} value={timeout} onChange={(event) => setTimeout(Number(event.target.value))} /></Field>
                <Field label="Max attempts (1–10)" htmlFor="attempts"><input id="attempts" className="input" type="number" min={1} max={10} value={maxAttempts} onChange={(event) => setMaxAttempts(Number(event.target.value))} /></Field>
                <Field label="Initial retry backoff (s)" htmlFor="initial-backoff"><input id="initial-backoff" className="input" type="number" min={0.1} max={60} step="0.1" value={initialBackoff} onChange={(event) => setInitialBackoff(Number(event.target.value))} /></Field>
                <Field label="Max retry backoff (s)" htmlFor="max-backoff"><input id="max-backoff" className="input" type="number" min={1} max={3600} value={maxBackoff} onChange={(event) => setMaxBackoff(Number(event.target.value))} /></Field>
                <Field label="Backoff multiplier" htmlFor="multiplier"><input id="multiplier" className="input" type="number" min={1} max={10} step="0.1" value={multiplier} onChange={(event) => setMultiplier(Number(event.target.value))} /></Field>
                <Field label="Schedule at (local time)" htmlFor="schedule"><input id="schedule" className="input" type="datetime-local" value={scheduleAt} onChange={(event) => setScheduleAt(event.target.value)} /></Field>
              </div>
              <div className="form-grid">
                <Field label="Configuration JSON" htmlFor="configuration"><textarea id="configuration" className="textarea" value={configuration} onChange={(event) => setConfiguration(event.target.value)} /></Field>
                <Field label="Metadata JSON" htmlFor="metadata"><textarea id="metadata" className="textarea" value={metadata} onChange={(event) => setMetadata(event.target.value)} /></Field>
              </div>
              <div className="form-help" style={{ marginBottom: 14 }}>Configuration and metadata must be JSON objects. Credential-like configuration keys are rejected by the API.</div>
            </div>
          )}
          {error && <div className="notice" role="alert" style={{ margin: "14px 0" }}><CircleAlert size={15} /><span>{error}</span></div>}
          <Button type="submit" variant="primary" disabled={submitting || !model.trim() || !prompt.trim()}>
            {submitting ? "Submitting to API…" : "Submit job"} {!submitting && <ArrowRight size={14} />}
          </Button>
        </section>

        <aside className="panel submit-summary">
          <div className="section-label">Request preview</div>
          <div className="summary-list">
            <Summary label="Type" value="structured_inference" />
            <Summary label="Model" value={model.trim() || "Not set"} />
            <Summary label="Priority" value={String(priority)} />
            <Summary label="Timeout" value={`${timeout}s`} />
            <Summary label="Retry budget" value={`${maxAttempts} attempts`} />
            <Summary label="Schedule" value={scheduleAt ? new Date(scheduleAt).toLocaleString() : "Immediate"} />
          </div>
          <div className="secret-safe-note" style={{ marginTop: 20 }}>
            <Clock3 size={13} style={{ verticalAlign: "middle", marginRight: 6 }} />
            Future schedules remain <code>ACCEPTED</code> until the backend scheduler activates them.
          </div>
          <div className="idempotency-note" style={{ marginTop: 14 }}>A fresh Idempotency-Key is sent for a new payload and reused only when retrying the exact same request.</div>
        </aside>
      </form>
    </>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return <label className="form-group" htmlFor={htmlFor}><span className="form-label">{label}</span>{children}</label>;
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="summary-item"><span>{label}</span><strong>{value}</strong></div>;
}

function Meta({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><div className="meta-label">{label}</div><div className={`meta-value ${mono ? "mono" : ""}`}>{value}</div></div>;
}
