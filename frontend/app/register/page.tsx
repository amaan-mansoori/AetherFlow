"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Activity, ArrowRight, Check, CircleAlert, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { api } from "@/lib/api/client";
import { explainApiError } from "@/lib/api/errors";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [registered, setRegistered] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 12 || password.length > 128 || !password.trim()) {
      setError("Use a password between 12 and 128 characters.");
      return;
    }
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.register(email.trim(), password);
      setRegistered(true);
    } catch (reason) {
      setError(explainApiError(reason));
    } finally {
      setSubmitting(false);
    }
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
            <div className="eyebrow"><span className="signal-dot" /> Account registration</div>
            <h1 className="login-context-title">Build with<br /><span>durable work.</span></h1>
            <p>Create a standard user account to submit asynchronous jobs and inspect the records your account owns.</p>
          </div>
        </section>

        <section className="login-shell" aria-labelledby="register-title">
          {registered ? (
            <div className="registration-success" aria-live="polite">
              <div className="eyebrow"><Check size={14} /> Account created</div>
              <h2 className="login-title" id="register-title">You&apos;re registered</h2>
              <p className="login-copy">Your account has standard user access. Sign in to continue; registration does not create a session.</p>
              <Link className="button primary" href="/login">Continue to sign in <ArrowRight size={15} /></Link>
            </div>
          ) : (
            <>
              <div className="eyebrow"><ShieldCheck size={14} /> Create an account</div>
              <h2 className="login-title" id="register-title">Sign up</h2>
              <p className="login-copy">Registration creates a standard account. Administrator access is assigned separately.</p>
              <form onSubmit={submit} noValidate>
                <label className="form-group">
                  <span className="form-label">Email address</span>
                  <input
                    className="input"
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={320}
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@company.com"
                  />
                </label>
                <label className="form-group">
                  <span className="form-label">Password</span>
                  <span className="password-control">
                    <input
                      className="input"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      minLength={12}
                      maxLength={128}
                      aria-label="Password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      aria-describedby="password-help"
                    />
                    <button className="password-toggle" type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((visible) => !visible)}>
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </span>
                  <span className="form-help" id="password-help">Use 12–128 characters. Passwords are hashed by the API and never returned.</span>
                </label>
                <label className="form-group">
                  <span className="form-label">Confirm password</span>
                  <span className="password-control">
                    <input
                      className="input"
                      type={showConfirmation ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      maxLength={128}
                      aria-label="Confirm password"
                      value={confirmation}
                      onChange={(event) => setConfirmation(event.target.value)}
                    />
                    <button className="password-toggle" type="button" aria-label={showConfirmation ? "Hide confirmation" : "Show confirmation"} onClick={() => setShowConfirmation((visible) => !visible)}>
                      {showConfirmation ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </span>
                </label>
                {error && <div className="notice" role="alert"><CircleAlert size={15} /><span>{error}</span></div>}
                <Button type="submit" variant="primary" disabled={submitting || !email || !password || !confirmation} style={{ width: "100%", marginTop: 8 }}>
                  {submitting ? "Creating account…" : "Create account"} {!submitting && <ArrowRight size={15} />}
                </Button>
              </form>
              <div className="auth-links">
                <span>Already registered? <Link href="/login">Sign in</Link></span>
              </div>
              <div className="login-foot">No email verification or password-recovery service is configured in this deployment.</div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
