import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { JobDetailClient } from "@/components/jobs/job-detail";
import type { AdminJobDetail, JobDetail, User } from "@/types/api";

const mocks = vi.hoisted(() => ({
  detail: vi.fn(),
  events: vi.fn(),
  attempts: vi.fn(),
  cancel: vi.fn(),
  adminDetail: vi.fn(),
  adminCancel: vi.fn(),
  show: vi.fn(),
  user: null as User | null,
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    jobs: {
      detail: mocks.detail,
      events: mocks.events,
      attempts: mocks.attempts,
      cancel: mocks.cancel,
    },
    admin: {
      detail: mocks.adminDetail,
      cancel: mocks.adminCancel,
    },
  },
}));
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({ user: mocks.user }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ show: mocks.show }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const account: User = {
  id: "user-1",
  email: "ops@example.com",
  roles: ["USER"],
  created_at: "2026-10-04T10:00:00Z",
  last_login_at: null,
};

const userJob: JobDetail = {
  id: "job-123",
  user_id: account.id,
  type: "structured_inference",
  model: "configured-model",
  state: "QUEUED",
  priority: 0,
  timeout_seconds: 300,
  version: 1,
  created_at: "2026-10-04T10:00:00Z",
  updated_at: "2026-10-04T10:00:00Z",
  schedule_at: null,
  input: { prompt: "A safe test prompt." },
  configuration: {},
  retry_policy: { max_attempts: 3 },
  metadata: {},
  result: null,
  latest_attempt: null,
};

function adminJob(): AdminJobDetail {
  return {
    id: userJob.id,
    user_id: userJob.user_id,
    type: userJob.type,
    model: userJob.model,
    state: userJob.state,
    priority: userJob.priority,
    timeout_seconds: userJob.timeout_seconds,
    version: userJob.version,
    created_at: userJob.created_at,
    updated_at: userJob.updated_at,
    schedule_at: userJob.schedule_at,
    retry_policy: userJob.retry_policy,
    metadata: userJob.metadata,
    execution_owner: null,
    execution_dispatch_version: null,
    execution_lease_until: null,
    attempts: [],
    events: [],
    dispatches: [],
  };
}

describe("job execution detail", () => {
  beforeEach(() => {
    mocks.detail.mockReset();
    mocks.events.mockReset();
    mocks.attempts.mockReset();
    mocks.cancel.mockReset();
    mocks.adminDetail.mockReset();
    mocks.adminCancel.mockReset();
    mocks.show.mockReset();
    mocks.user = account;
    mocks.detail.mockResolvedValue(userJob);
    mocks.events.mockResolvedValue([]);
    mocks.attempts.mockResolvedValue([]);
  });

  it("renders the observed state and cancels only after explicit confirmation", async () => {
    mocks.detail
      .mockResolvedValueOnce(userJob)
      .mockResolvedValue({ ...userJob, state: "CANCEL_REQUESTED" });
    mocks.cancel.mockResolvedValue({ ...userJob, state: "CANCEL_REQUESTED" });
    render(<JobDetailClient jobId="job-123" />);

    expect(await screen.findByText("structured_inference")).toBeInTheDocument();
    expect(screen.getByLabelText("State: QUEUED")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel job" }));
    expect(mocks.cancel).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Request cancellation" }));

    await waitFor(() => expect(mocks.cancel).toHaveBeenCalledOnce());
    expect(mocks.cancel).toHaveBeenCalledWith("job-123");
    await waitFor(() => expect(screen.getByLabelText("State: CANCEL REQUESTED")).toBeInTheDocument());
  });

  it("distinguishes persisted lifecycle states and marks the current observed state", async () => {
    mocks.detail.mockResolvedValue({ ...userJob, state: "FAILED" });
    mocks.events.mockResolvedValue([
      {
        id: "event-queued",
        job_id: userJob.id,
        event_type: "job.queued",
        prior_state: "ACCEPTED",
        next_state: "QUEUED",
        actor: "api",
        payload: {},
        created_at: userJob.created_at,
      },
      {
        id: "event-failed",
        job_id: userJob.id,
        event_type: "job.failed",
        prior_state: "RUNNING",
        next_state: "FAILED",
        actor: "worker",
        payload: {},
        created_at: userJob.updated_at,
      },
    ]);
    render(<JobDetailClient jobId={userJob.id} />);

    const current = await screen.findByLabelText("Latest event matches current job state");
    expect(current).toHaveClass("timeline-marker", "state-failed");
    expect(current.closest(".timeline-event")).toHaveClass("current");
    expect(document.querySelector(".timeline-marker.state-queued")).not.toHaveClass("current");
  });

  it("uses the admin detail API and never renders user-only job input", async () => {
    mocks.user = { ...account, roles: ["USER", "ADMIN"] };
    mocks.adminDetail.mockResolvedValue(adminJob());
    render(<JobDetailClient jobId="job-123" />);

    expect(await screen.findByText("structured_inference")).toBeInTheDocument();
    expect(mocks.adminDetail).toHaveBeenCalledWith("job-123", expect.any(AbortSignal));
    expect(screen.getByText(/administrative API does not return job input/)).toBeInTheDocument();
    expect(screen.queryByText("Submitted input")).not.toBeInTheDocument();
    expect(mocks.detail).not.toHaveBeenCalled();
  });
});
