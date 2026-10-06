import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api/client";
import type { AuthResponse, User } from "@/types/api";

const user: User = {
  id: "user-1",
  email: "ops@example.com",
  roles: ["USER"],
  created_at: "2026-10-04T10:00:00Z",
  last_login_at: null,
};

function auth(token: string): AuthResponse {
  return { access_token: token, token_type: "bearer", expires_in: 900, user };
}

describe("central API client", () => {
  it("logs in using the HttpOnly-cookie-compatible credential mode and keeps access tokens in memory", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(auth("access-memory")), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const response = await api.login("ops@example.com", "password");
    api.setSession(response);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("http://localhost:8000/api/v1/auth/login"),
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(options.headers).has("Authorization")).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(api.currentSession().token).toBe("access-memory");
  });

  it("registers without attaching credentials or creating a session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(user), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const created = await api.register(user.email, "a long registration password");

    expect(created).toEqual(user);
    expect(api.currentSession()).toEqual({ token: null, user: null });
    const [requestUrl, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(requestUrl).toContain("/api/v1/auth/register");
    expect(options.method).toBe("POST");
    expect(new Headers(options.headers).has("Authorization")).toBe(false);
    expect(JSON.parse(String(options.body))).toEqual({
      email: user.email,
      password: "a long registration password",
    });
  });

  it("checks demo availability without requiring an authenticated session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ available: false, access_mode: "read-only" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.demoStatus()).resolves.toEqual({
      available: false,
      access_mode: "read-only",
    });
    const [requestUrl, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(requestUrl).toContain("/api/v1/auth/demo");
    expect(new Headers(options.headers).has("Authorization")).toBe(false);
  });

  it("refreshes once after 401 and retries with the rotated bearer token", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "AUTHENTICATION_REQUIRED", message: "Authentication is required.", request_id: null, details: {} } }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(auth("rotated-token")), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: user.id, email: user.email, roles: user.roles, created_at: user.created_at, last_login_at: null }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    api.setSession(auth("expired-token"));
    const me = await api.me();
    expect(me.email).toBe("ops@example.com");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const refreshOptions = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(refreshOptions.credentials).toBe("include");
    expect(new Headers(refreshOptions.headers).has("Authorization")).toBe(false);
    const retryOptions = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect(new Headers(retryOptions.headers).get("Authorization")).toBe("Bearer rotated-token");
    expect(api.currentSession().token).toBe("rotated-token");
  });

  it("uses the bounded list API parameters and the admin cancellation route", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    api.setSession(auth("access"));
    await api.jobs.list({ state: "FAILED", limit: 25, offset: 50 });
    await api.admin.cancel("job-123");
    expect(fetchMock.mock.calls[0]?.[0]).toContain("state=FAILED");
    expect(fetchMock.mock.calls[0]?.[0]).toContain("limit=25");
    expect(fetchMock.mock.calls[0]?.[0]).toContain("offset=50");
    expect(fetchMock.mock.calls[1]?.[0]).toContain("/api/v1/admin/jobs/job-123/cancel");
  });

  it("submits the typed job body with an idempotency key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "job-123" }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    api.setSession(auth("access"));
    const payload = {
      type: "structured_inference",
      model: "configured-model",
      input: { prompt: "Summarize this." },
      configuration: {},
      priority: 0,
      timeout_seconds: 300,
      retry_policy: {
        max_attempts: 3,
        initial_backoff_seconds: 1,
        max_backoff_seconds: 60,
        backoff_multiplier: 2,
        jitter: true,
      },
      metadata: {},
      schedule_at: null,
    };
    await api.jobs.create(payload, "stable-idempotency-key");
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(options.headers).get("Idempotency-Key")).toBe("stable-idempotency-key");
    expect(JSON.parse(String(options.body))).toEqual(payload);
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/v1/jobs");
  });

  it("honors Retry-After by suppressing immediate follow-up network requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "RATE_LIMITED",
            message: "Too many requests.",
            request_id: null,
            details: {},
          },
        }),
        { status: 429, headers: { "Retry-After": "30" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    api.setSession(auth("access"));
    await expect(api.jobs.list()).rejects.toMatchObject({ status: 429, retryAfterSeconds: 30 });
    await expect(api.jobs.list()).rejects.toMatchObject({ status: 429, retryAfterSeconds: 30 });
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
