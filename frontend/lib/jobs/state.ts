import type { JobState } from "@/types/api";

export const TERMINAL_STATES: ReadonlySet<JobState> = new Set([
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
  "DEAD_LETTERED",
]);

export const CANCELLABLE_STATES: ReadonlySet<JobState> = new Set([
  "ACCEPTED",
  "QUEUED",
  "RUNNING",
  "RETRY_SCHEDULED",
]);

export function canCancel(state: JobState): boolean {
  return CANCELLABLE_STATES.has(state);
}

export function isTerminal(state: JobState): boolean {
  return TERMINAL_STATES.has(state);
}

export function isScheduled(state: JobState, scheduleAt: string | null): boolean {
  return state === "ACCEPTED" && scheduleAt !== null && Date.parse(scheduleAt) > Date.now();
}

export function formatState(state: JobState): string {
  return state.replaceAll("_", " ");
}
