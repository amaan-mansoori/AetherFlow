"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Activity, ArrowRight, CircleAlert, Clock3, Database, KeyRound, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/primitives";
import { ApiError, explainApiError } from "@/lib/api/errors";
import { api } from "@/lib/api/client";
import { safeReturnPath } from "@/lib/auth/return-path";

export default function LoginPage() {
  const { status, signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [demoAvailability, setDemoAvailability] = useState<"checking" | "available" | "unavailable" | "unknown">("checking");

  useEffect(() => {
    if (status === "authenticated") {
      const next = safeReturnPath(new URLSearchParams(window.location.search).get("next"));
      router.replace(next ?? "/");
    }
  }, [status, router]);

  useEffect(() => {
    const controller = new AbortController();
    void api.demoStatus(controller.signal)
      .then((result) => setDemoAvailability(result.available ? "available" : "unavailable"))
      .catch(() => setDemoAvailability("unknown"));
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(email.trim(), password);
      const next = safeReturnPath(new URLSearchParams(window.location.search).get("next"));
      router.replace(next ?? "/");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : explainApiError(reason));
    } finally {
      setSubmitting(false);
    }
  }

  if (status === "loading" || status === "authenticated") {
    return <div className="center-state"><span className="screen-spinner" aria-label="Restoring session" /></div>;
  }

  return (
    <main className="login-screen">
      <div className="login-layout">
        <section className="login-context" aria-label="AetherFlow platform">
          <div className="login-brand">
            <span className="login-mark"><Activity size={18} strokeWidth={1.8} /></span>
            <span>
              <strong className="brand-word">AETHERFLOW</strong>
              <span className="brand-caption" style={{ display: "block", marginTop: 2 }}>JOB ORCHESTRATION</span>
            </span>
          </div>
          <div className="login-context-main">
            <div className="eyebrow"><span className="signal-dot" /> Distributed job control</div>
            <h1 className="login-context-title">Durable work.<br /><span>Clear execution.</span></h1>
            <p>Submit asynchronous inference jobs, follow persisted state transitions, and inspect outcomes from the system of record.</p>
          </div>
          <div className="login-capabilities" aria-label="Platform capabilities">
            <div><Database size={15} /><span><small>01 / PERSISTENCE</small><strong>Durable job records</strong></span></div>
            <div><Activity size={15} /><span><small>02 / EXECUTION</small><strong>Observed lifecycle</strong></span></div>
            <div><Clock3 size={15} /><span><small>03 / CONTROL</small><strong>Backend-owned scheduling</strong></span></div>
          </div>
          <div className="login-context-footer"><span>AETHERFLOW / OPERATIONS</span><span>AUTHENTICATED ACCESS</span></div>
        </section>

        <section className="login-shell" aria-labelledby="login-title">
          <div className="eyebrow"><ShieldCheck size={14} /> Account access</div>
          <h2 className="login-title" id="login-title">Sign in</h2>
          <p className="login-copy">Use your AetherFlow account to continue.</p>
          <form onSubmit={submit} noValidate>
            <label className="form-group">
              <span className="form-label">Email address</span>
              <input
                className="input"
                type="email"
                autoComplete="username"
                required
                maxLength={320}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
                aria-label="Email address"
              />
            </label>
            <label className="form-group">
              <span className="form-label">Password</span>
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                required
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Your account password"
                aria-label="Password"
              />
            </label>
            {error && <div className="notice" role="alert"><CircleAlert size={15} /><span>{error}</span></div>}
            <Button type="submit" variant="primary" disabled={submitting || !email || !password} style={{ width: "100%", marginTop: 8 }}>
              {submitting ? "Authenticating…" : "Continue"} {!submitting && <ArrowRight size={15} />}
            </Button>
          </form>
          <div className="login-foot">
            <KeyRound size={12} style={{ verticalAlign: "middle", marginRight: 5 }} />
            Access tokens stay in memory. Session recovery uses the backend&apos;s HttpOnly refresh cookie.
          </div>
          <div className="auth-links">
            <span>New to AetherFlow? <Link href="/register">Create an account</Link></span>
            {demoAvailability === "available" ? (
              <Link href="/demo">Try the read-only demo</Link>
            ) : demoAvailability === "unavailable" ? (
              <span className="muted" role="status">Demo access is not enabled or provisioned here.</span>
            ) : demoAvailability === "unknown" ? (
              <span className="muted" role="status">Demo availability could not be checked.</span>
            ) : null}
          </div>
        </section>
      </div>
    </main>
  );
}
