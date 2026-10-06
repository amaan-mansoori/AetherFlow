import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StatusBadge, ConfirmDialog } from "@/components/ui/primitives";
import { canAccessAdmin } from "@/lib/auth/access";
import { buildSubmission } from "@/lib/jobs/submission";
import type { User } from "@/types/api";

const account: User = {
  id: "user-1",
  email: "ops@example.com",
  roles: ["USER"],
  created_at: "2026-10-04T10:00:00Z",
  last_login_at: null,
};

describe("operations UI primitives", () => {
  it("renders real backend states with accessible labels", () => {
    render(<StatusBadge state="RETRY_SCHEDULED" />);
    expect(screen.getByLabelText("State: RETRY SCHEDULED")).toBeInTheDocument();
  });

  it("requires an explicit confirmation action before invoking cancellation", () => {
    const confirm = vi.fn();
    render(
      <ConfirmDialog open title="Request job cancellation?" confirmLabel="Request cancellation" onCancel={vi.fn()} onConfirm={confirm}>
        Confirm the target operation.
      </ConfirmDialog>,
    );
    expect(confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Request cancellation" }));
    expect(confirm).toHaveBeenCalledOnce();
  });

  it("exposes admin navigation only for an ADMIN role", () => {
    expect(canAccessAdmin(account)).toBe(false);
    expect(canAccessAdmin({ ...account, roles: ["USER", "ADMIN"] })).toBe(true);
    expect(canAccessAdmin(null)).toBe(false);
  });

  it("builds the exact structured inference request and rejects invalid JSON", () => {
    const submission = buildSubmission({
      model: "configured-model",
      prompt: "Summarize this.",
      configuration: "{}",
      metadata: "{\"source\":\"console\"}",
      priority: 2,
      timeout: 120,
      maxAttempts: 2,
      initialBackoff: 1,
      maxBackoff: 30,
      multiplier: 2,
      scheduleAt: "",
    });
    expect(submission.type).toBe("structured_inference");
    expect(submission.input).toEqual({ prompt: "Summarize this." });
    expect(submission.schedule_at).toBeNull();
    expect(() => buildSubmission({
      model: "configured-model",
      prompt: "Prompt",
      configuration: "[",
      metadata: "{}",
      priority: 0,
      timeout: 300,
      maxAttempts: 3,
      initialBackoff: 1,
      maxBackoff: 60,
      multiplier: 2,
      scheduleAt: "",
    })).toThrow("Configuration must be valid JSON.");
  });
});
