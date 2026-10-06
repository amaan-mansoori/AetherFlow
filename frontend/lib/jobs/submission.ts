import type { JobSubmission } from "@/types/api";

export function parseObjectJson(value: string, label: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

export function buildSubmission(input: {
  model: string;
  prompt: string;
  configuration: string;
  metadata: string;
  priority: number;
  timeout: number;
  maxAttempts: number;
  initialBackoff: number;
  maxBackoff: number;
  multiplier: number;
  scheduleAt: string;
}): JobSubmission {
  if (!input.model.trim()) throw new Error("Enter a model identifier.");
  if (!input.prompt.trim()) throw new Error("Enter a prompt for structured inference.");
  return {
    type: "structured_inference",
    model: input.model.trim(),
    input: { prompt: input.prompt },
    configuration: parseObjectJson(input.configuration, "Configuration"),
    priority: input.priority,
    timeout_seconds: input.timeout,
    retry_policy: {
      max_attempts: input.maxAttempts,
      initial_backoff_seconds: input.initialBackoff,
      max_backoff_seconds: input.maxBackoff,
      backoff_multiplier: input.multiplier,
      jitter: true,
    },
    metadata: parseObjectJson(input.metadata, "Metadata"),
    schedule_at: input.scheduleAt ? new Date(input.scheduleAt).toISOString() : null,
  };
}
