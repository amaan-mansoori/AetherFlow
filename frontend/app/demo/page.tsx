"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, CircleAlert, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api/client";
import type { DemoAccessStatus } from "@/types/api";

type DemoState =
  | { status: "loading" }
  | { status: "available"; data: DemoAccessStatus }
  | { status: "unavailable" }
  | { status: "error"; message: string };

export default function DemoPage() {
  const [state, setState] = useState<DemoState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    void api.demoStatus(controller.signal).then((result) => {
      setState(result.available ? { status: "available", data: result } : { status: "unavailable" });
    }).catch(() => {
      if (!controller.signal.aborted) {
        setState({ status: "error", message: "Demo availability could not be confirmed. Try again later." });
      }
    });
    return () => controller.abort();
  }, []);

  return (
    <main className="login-screen">
      <section className="login-shell demo-access" aria-labelledby="demo-title">
        <div className="login-brand" style={{ marginBottom: 28 }}>
          <span className="login-mark"><Activity size={18} strokeWidth={1.8} /></span>
          <span><strong className="brand-word">AETHERFLOW</strong><span className="brand-caption" style={{ display: "block", marginTop: 2 }}>JOB ORCHESTRATION</span></span>
        </div>
        <div className="eyebrow"><ShieldCheck size={14} /> Recruiter access</div>
        <h1 className="login-title" id="demo-title">Read-only demo</h1>
        {state.status === "loading" ? (
          <p className="login-copy" role="status">Checking whether this environment has a demo workspace…</p>
        ) : state.status === "error" ? (
          <div className="notice" role="alert"><CircleAlert size={15} /><span>{state.message}</span></div>
        ) : state.status === "unavailable" ? (
          <div className="notice warning" role="status"><CircleAlert size={15} /><span>Demo access is unavailable. The operator has not enabled and provisioned a demo account in this environment.</span></div>
        ) : (
          <>
            <p className="login-copy">This dedicated DEMO account can inspect its own seeded examples. It cannot submit or cancel jobs, create API keys, or access admin operations.</p>
            <div className="demo-details">
              <div><span>Account</span><code>recruiter-demo@example.com</code></div>
              <div><span>Access</span><strong>Read-only</strong></div>
              <div><span>Sample records</span><strong>Scheduled and cancellation-requested fixtures</strong></div>
            </div>
            <p className="form-help">Use the demo password supplied by the environment operator. It is never displayed or bundled in this application.</p>
            <Link className="button primary" href="/login">Continue to sign in <ArrowRight size={15} /></Link>
          </>
        )}
        <div className="auth-links"><Link href="/login">Back to sign in</Link><Link href="/register">Create an account</Link></div>
      </section>
    </main>
  );
}
