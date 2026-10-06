import { describe, expect, it } from "vitest";
import { explainApiError, parseApiError } from "@/lib/api/errors";

describe("API error contract", () => {
  it("maps the structured error envelope and Retry-After", async () => {
    const response = new Response(
      JSON.stringify({
        error: {
          code: "RATE_LIMITED",
          message: "Slow down.",
          request_id: "req-safe",
          details: {},
        },
      }),
      { status: 429, headers: { "Retry-After": "17", "Content-Type": "application/json" } },
    );
    const error = await parseApiError(response);
    expect(error.code).toBe("RATE_LIMITED");
    expect(error.requestId).toBe("req-safe");
    expect(error.retryAfterSeconds).toBe(17);
    expect(explainApiError(error)).toContain("17 seconds");
  });

  it("does not surface an arbitrary server response body as an error", async () => {
    const error = await parseApiError(new Response("<html>internal trace</html>", { status: 500 }));
    expect(explainApiError(error)).toBe("The service could not complete the request.");
    expect(explainApiError(error)).not.toContain("internal trace");
  });
});
