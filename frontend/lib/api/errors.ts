import type { ApiErrorBody } from "@/types/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: Record<string, unknown>;
  readonly retryAfterSeconds: number | null;

  constructor(
    message: string,
    options: {
      status: number;
      code: string;
      requestId?: string | null;
      details?: Record<string, unknown>;
      retryAfterSeconds?: number | null;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId ?? null;
    this.details = options.details ?? {};
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }
}

function retryAfter(response: Response): number | null {
  const value = response.headers.get("Retry-After");
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds);
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let payload: Partial<ApiErrorBody> = {};
  try {
    payload = (await response.json()) as Partial<ApiErrorBody>;
  } catch {
    payload = {};
  }
  const error = payload.error;
  const safeMessage =
    typeof error?.message === "string"
      ? error.message
      : response.status === 429
        ? "The service is rate limiting requests. Wait before trying again."
        : response.status >= 500
          ? "The service could not complete the request."
          : "The request could not be completed.";
  return new ApiError(safeMessage, {
    status: response.status,
    code: typeof error?.code === "string" ? error.code : "HTTP_ERROR",
    requestId: typeof error?.request_id === "string" ? error.request_id : null,
    details:
      error?.details && typeof error.details === "object" ? error.details : {},
    retryAfterSeconds: retryAfter(response),
  });
}

export function explainApiError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "VALIDATION_ERROR") return error.message || "Check the highlighted fields.";
    if (error.code === "AUTHENTICATION_REQUIRED") return "Your session expired. Sign in again.";
    if (error.code === "FORBIDDEN") return "Your account does not have permission for this operation.";
    if (error.code === "NOT_FOUND") return "This job is no longer available.";
    if (error.code === "CONFLICT" || error.code === "INVALID_STATE_TRANSITION") {
      return "The job changed before this action completed. Refresh the latest state.";
    }
    if (error.code === "RATE_LIMITED") {
      return error.retryAfterSeconds === null
        ? "Too many requests. Wait briefly before trying again."
        : `Too many requests. Try again in about ${error.retryAfterSeconds} seconds.`;
    }
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "The request was cancelled.";
  }
  if (error instanceof TypeError) return "The API could not be reached. Check connectivity and try again.";
  return "Something unexpected happened. Try again.";
}
