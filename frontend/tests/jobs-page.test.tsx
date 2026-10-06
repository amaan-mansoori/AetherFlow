import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import JobsPage from "@/app/(console)/jobs/page";
import type { JobSummary } from "@/types/api";

const { list } = vi.hoisted(() => ({ list: vi.fn() }));

vi.mock("@/lib/api/client", () => ({
  api: { jobs: { list } },
}));
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({
    user: {
      id: "user-1",
      email: "ops@example.com",
      roles: ["USER"],
      created_at: "2026-10-04T10:00:00Z",
      last_login_at: null,
    },
  }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

function job(id: string, state: JobSummary["state"], model = "model-a"): JobSummary {
  return {
    id,
    user_id: "user-1",
    type: "structured_inference",
    model,
    state,
    priority: 0,
    timeout_seconds: 300,
    version: 1,
    created_at: "2026-10-04T10:00:00Z",
    updated_at: "2026-10-04T10:00:00Z",
    schedule_at: null,
  };
}

describe("jobs page", () => {
  beforeEach(() => {
    list.mockReset();
  });

  it("sends state filters to the API and searches only the returned page", async () => {
    list
      .mockResolvedValueOnce([job("job-a", "SUCCEEDED"), job("job-b", "FAILED", "model-b")])
      .mockResolvedValueOnce([job("job-b", "FAILED", "model-b")]);
    render(<JobsPage />);

    await screen.findByText(/job-a · model-a/);
    fireEvent.change(screen.getByLabelText("Filter by state"), { target: { value: "FAILED" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(
      { state: "FAILED", limit: 20, offset: 0 },
      expect.any(AbortSignal),
    ));
    expect(await screen.findByText(/job-b · model-b/)).toBeInTheDocument();
    expect(screen.queryByText(/job-a · model-a/)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search visible jobs"), { target: { value: "no-match" } });
    expect(screen.getByText("No jobs match this view")).toBeInTheDocument();
  });

  it("requests the next bounded offset page", async () => {
    list
      .mockResolvedValueOnce(Array.from({ length: 20 }, (_, index) => job(`job-${index}`, "QUEUED")))
      .mockResolvedValueOnce([]);
    render(<JobsPage />);

    await screen.findByText(/job-0 · model-a/);
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(
      { state: undefined, limit: 20, offset: 20 },
      expect.any(AbortSignal),
    ));
  });
});
