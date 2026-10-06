export const JOB_STATES = [
  "ACCEPTED",
  "QUEUED",
  "RUNNING",
  "RETRY_SCHEDULED",
  "DEAD_LETTERED",
  "CANCEL_REQUESTED",
  "CANCELLED",
  "SUCCEEDED",
  "FAILED",
] as const;

export type JobState = (typeof JOB_STATES)[number];

export interface User {
  id: string;
  email: string;
  roles: string[];
  created_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export interface DemoAccessStatus {
  available: boolean;
  access_mode: "read-only";
}

export interface JobSummary {
  id: string;
  user_id: string;
  type: string;
  model: string;
  state: JobState;
  priority: number;
  timeout_seconds: number;
  version: number;
  created_at: string;
  updated_at: string;
  schedule_at: string | null;
}

export interface JobAttempt {
  id: string;
  job_id: string;
  attempt_number: number;
  status: string;
  worker_id: string | null;
  provider: string | null;
  model: string | null;
  error_class: string | null;
  error_message: string | null;
  retry_decision: string | null;
  usage: Record<string, unknown> | null;
  trace_id: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface JobEvent {
  id: string;
  job_id: string;
  event_type: string;
  prior_state: JobState | null;
  next_state: JobState;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface JobResult {
  id: string;
  job_id: string;
  schema_version: string;
  output: Record<string, unknown>;
  usage: Record<string, unknown> | null;
  created_at: string;
}

export interface JobDetail extends JobSummary {
  input: Record<string, unknown>;
  configuration: Record<string, unknown>;
  retry_policy: Record<string, unknown>;
  metadata: Record<string, unknown>;
  result: JobResult | null;
  latest_attempt: JobAttempt | null;
}

export interface AdminDispatch {
  id: string;
  job_id: string;
  job_version: number;
  message_type: string;
  schema_version: string;
  enqueued_at: string;
  created_at: string;
  published_at: string | null;
  attempt_count: number;
  failure_category: string | null;
  publication_state: string;
  available_at: string | null;
  next_attempt_at: string | null;
  last_error: string | null;
}

export interface AdminJobDetail extends JobSummary {
  retry_policy: Record<string, unknown>;
  metadata: Record<string, unknown>;
  execution_owner: string | null;
  execution_dispatch_version: number | null;
  execution_lease_until: string | null;
  attempts: JobAttempt[];
  events: JobEvent[];
  dispatches: AdminDispatch[];
}

export interface JobSubmission {
  type: string;
  model: string;
  input: Record<string, unknown>;
  configuration: Record<string, unknown>;
  priority: number;
  timeout_seconds: number;
  retry_policy: {
    max_attempts: number;
    initial_backoff_seconds: number;
    max_backoff_seconds: number;
    backoff_multiplier: number;
    jitter: boolean;
  };
  metadata: Record<string, unknown>;
  schedule_at: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details: Record<string, unknown>;
  };
}

export interface HealthResponse {
  status: string;
  database?: string;
}

export interface MetricsSnapshot {
  counters: Record<string, number>;
}
