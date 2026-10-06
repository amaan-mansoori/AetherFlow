import { ApiError, parseApiError } from "@/lib/api/errors";
import type {
  AdminJobDetail,
  AuthResponse,
  DemoAccessStatus,
  HealthResponse,
  JobAttempt,
  JobDetail,
  JobEvent,
  JobState,
  JobSubmission,
  JobSummary,
  MetricsSnapshot,
  User,
} from "@/types/api";

type SessionListener = (token: string | null, user: User | null) => void;
type QueryValue = string | number | undefined | null;

const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);
const sessionListeners = new Set<SessionListener>();
let accessToken: string | null = null;
let sessionUser: User | null = null;
let refreshPromise: Promise<AuthResponse> | null = null;
let rateLimitUntil = 0;

function updateSession(token: string | null, user: User | null): void {
  accessToken = token;
  sessionUser = user;
  for (const listener of sessionListeners) listener(token, user);
}

function url(path: string): string {
  return `${baseUrl}${path}`;
}

function queryString(values: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function requestRaw<T>(
  path: string,
  init: RequestInit,
  token: string | null,
): Promise<T> {
  const remainingSeconds = Math.ceil((rateLimitUntil - Date.now()) / 1000);
  if (remainingSeconds > 0) {
    throw new ApiError("The service is rate limiting requests.", {
      status: 429,
      code: "RATE_LIMITED",
      retryAfterSeconds: remainingSeconds,
    });
  }
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(url(path), {
      ...init,
      headers,
      credentials: "include",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new TypeError("API request failed.");
  }
  if (!response.ok) {
    const error = await parseApiError(response);
    if (response.status === 429) {
      rateLimitUntil = Math.max(
        rateLimitUntil,
        Date.now() + (error.retryAfterSeconds ?? 1) * 1000,
      );
    }
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function refresh(): Promise<AuthResponse> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = requestRaw<AuthResponse>(
    "/api/v1/auth/refresh",
    { method: "POST" },
    null,
  )
    .then((data) => {
      updateSession(data.access_token, data.user);
      return data;
    })
    .catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 401) updateSession(null, null);
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { authenticated?: boolean; retryUnauthorized?: boolean } = {},
): Promise<T> {
  const authenticated = options.authenticated ?? true;
  const retryUnauthorized = options.retryUnauthorized ?? true;
  if (authenticated && !accessToken) {
    throw new ApiError("Your session has expired.", {
      status: 401,
      code: "AUTHENTICATION_REQUIRED",
    });
  }
  try {
    return await requestRaw<T>(path, init, authenticated ? accessToken : null);
  } catch (error) {
    if (
      !(error instanceof ApiError) ||
      error.status !== 401 ||
      !authenticated ||
      !retryUnauthorized ||
      init.signal?.aborted
    ) {
      throw error;
    }
    const renewed = await refresh();
    try {
      return await requestRaw<T>(path, init, renewed.access_token);
    } catch (retryError) {
      if (retryError instanceof ApiError && retryError.status === 401) {
        updateSession(null, null);
      }
      throw retryError;
    }
  }
}

export const api = {
  subscribe(listener: SessionListener): () => void {
    sessionListeners.add(listener);
    return () => {
      sessionListeners.delete(listener);
    };
  },
  currentSession(): { token: string | null; user: User | null } {
    return { token: accessToken, user: sessionUser };
  },
  setSession(data: AuthResponse): void {
    updateSession(data.access_token, data.user);
  },
  clearSession(): void {
    updateSession(null, null);
  },
  login(email: string, password: string, signal?: AbortSignal): Promise<AuthResponse> {
    return request<AuthResponse>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }), signal },
      { authenticated: false, retryUnauthorized: false },
    );
  },
  register(email: string, password: string, signal?: AbortSignal): Promise<User> {
    return request<User>(
      "/api/v1/auth/register",
      { method: "POST", body: JSON.stringify({ email, password }), signal },
      { authenticated: false, retryUnauthorized: false },
    );
  },
  demoStatus(signal?: AbortSignal): Promise<DemoAccessStatus> {
    return request<DemoAccessStatus>(
      "/api/v1/auth/demo",
      { signal },
      { authenticated: false, retryUnauthorized: false },
    );
  },
  async refreshSession(): Promise<AuthResponse> {
    return refresh();
  },
  async logout(): Promise<void> {
    try {
      await request<void>(
        "/api/v1/auth/logout",
        { method: "POST" },
        { authenticated: false, retryUnauthorized: false },
      );
    } finally {
      updateSession(null, null);
    }
  },
  me(signal?: AbortSignal): Promise<User> {
    return request<User>("/api/v1/auth/me", { signal });
  },
  jobs: {
    list(
      options: { state?: JobState; limit?: number; offset?: number } = {},
      signal?: AbortSignal,
    ): Promise<JobSummary[]> {
      return request<JobSummary[]>(
        `/api/v1/jobs${queryString({
          state: options.state,
          limit: options.limit ?? 20,
          offset: options.offset ?? 0,
        })}`,
        { signal },
      );
    },
    detail(id: string, signal?: AbortSignal): Promise<JobDetail> {
      return request<JobDetail>(`/api/v1/jobs/${encodeURIComponent(id)}`, { signal });
    },
    events(
      id: string,
      options: { limit?: number; offset?: number } = {},
      signal?: AbortSignal,
    ): Promise<JobEvent[]> {
      return request<JobEvent[]>(
        `/api/v1/jobs/${encodeURIComponent(id)}/events${queryString({
          limit: options.limit ?? 100,
          offset: options.offset ?? 0,
        })}`,
        { signal },
      );
    },
    attempts(
      id: string,
      options: { limit?: number; offset?: number } = {},
      signal?: AbortSignal,
    ): Promise<JobAttempt[]> {
      return request<JobAttempt[]>(
        `/api/v1/jobs/${encodeURIComponent(id)}/attempts${queryString({
          limit: options.limit ?? 100,
          offset: options.offset ?? 0,
        })}`,
        { signal },
      );
    },
    create(
      payload: JobSubmission,
      idempotencyKey: string,
      signal?: AbortSignal,
    ): Promise<JobDetail> {
      return request<JobDetail>(
        "/api/v1/jobs",
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey },
          body: JSON.stringify(payload),
          signal,
        },
      );
    },
    cancel(id: string, signal?: AbortSignal): Promise<JobDetail> {
      return request<JobDetail>(`/api/v1/jobs/${encodeURIComponent(id)}/cancel`, {
        method: "POST",
        signal,
      });
    },
  },
  admin: {
    list(
      filters: {
        job_id?: string;
        user_id?: string;
        state?: JobState;
        model?: string;
        provider?: string;
        created_from?: string;
        created_to?: string;
        schedule_from?: string;
        schedule_to?: string;
        priority?: number;
        limit?: number;
        offset?: number;
      },
      signal?: AbortSignal,
    ): Promise<JobSummary[]> {
      return request<JobSummary[]>(`/api/v1/admin/jobs${queryString(filters)}`, { signal });
    },
    detail(id: string, signal?: AbortSignal): Promise<AdminJobDetail> {
      return request<AdminJobDetail>(`/api/v1/admin/jobs/${encodeURIComponent(id)}`, {
        signal,
      });
    },
    cancel(id: string, signal?: AbortSignal): Promise<AdminJobDetail> {
      return request<AdminJobDetail>(`/api/v1/admin/jobs/${encodeURIComponent(id)}/cancel`, {
        method: "POST",
        signal,
      });
    },
  },
  health: {
    live(signal?: AbortSignal): Promise<HealthResponse> {
      return request<HealthResponse>("/health/live", { signal }, { authenticated: false });
    },
    ready(signal?: AbortSignal): Promise<HealthResponse> {
      return request<HealthResponse>("/health/ready", { signal }, { authenticated: false });
    },
    async metrics(signal?: AbortSignal): Promise<MetricsSnapshot> {
      const response = await fetch(url("/metrics"), { signal, credentials: "omit" });
      if (!response.ok) throw await parseApiError(response);
      const text = await response.text();
      const counters: Record<string, number> = {};
      for (const line of text.split("\n")) {
        const match = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^}]*\})?\s+([0-9.eE+-]+)$/.exec(line);
        if (
          match &&
          !["_sum", "_count", "_bucket"].some((suffix) => match[1].endsWith(suffix))
        ) {
          counters[match[1]] = (counters[match[1]] ?? 0) + Number(match[2]);
        }
      }
      return { counters };
    },
  },
};

export function buildQueryString(values: Record<string, QueryValue>): string {
  return queryString(values);
}
