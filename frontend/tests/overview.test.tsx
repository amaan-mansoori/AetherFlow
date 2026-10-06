import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import OverviewPage from "@/app/(console)/page";
import type { JobSummary } from "@/types/api";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  live: vi.fn(),
  ready: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    jobs: { list: mocks.list },
    health: { live: mocks.live, ready: mocks.ready },
  },
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

function job(id: string, state: JobSummary["state"], schedule_at: string | null = null): JobSummary {
  return {
    id,
    user_id: "user-1",
    type: "structured_inference",
    model: "model-a",
    state,
    priority: 0,
    timeout_seconds: 300,
    version: 1,
    created_at: "2026-10-04T10:00:00Z",
    updated_at: "2026-10-04T10:00:00Z",
    schedule_at,
  };
}

function expectMetricValue(label: string, value: number) {
  const metric = [...document.querySelectorAll<HTMLElement>(".metric")]
    .find((item) => item.querySelector(".metric-top")?.textContent === label);
  if (!metric) throw new Error(`Metric not found: ${label}`);
  expect(within(metric).getByText(String(value))).toBeInTheDocument();
}

describe("overview", () => {
  beforeEach(() => {
    mocks.list.mockReset();
    mocks.live.mockReset();
    mocks.ready.mockReset();
    mocks.live.mockResolvedValue({ status: "alive" });
    mocks.ready.mockResolvedValue({ status: "ready", database: "ok" });
  });

  it("reports exact sample counts and keeps failed states individually visible", async () => {
    mocks.list.mockResolvedValue([
      job("queued-job", "QUEUED"),
      job("scheduled-job", "ACCEPTED", "2099-01-01T10:00:00Z"),
      job("failed-job", "FAILED"),
      job("dead-job", "DEAD_LETTERED"),
      job("succeeded-job", "SUCCEEDED"),
    ]);
    render(<OverviewPage />);

    await screen.findByText("5");
    expectMetricValue("Recent jobs", 5);
    expectMetricValue("Non-terminal", 2);
    expectMetricValue("Needs attention", 2);
    expectMetricValue("Scheduled", 1);
    expect(screen.getAllByLabelText("State: FAILED")).toHaveLength(2);
    expect(screen.getAllByLabelText("State: DEAD LETTERED")).toHaveLength(2);
    expect(screen.getByText(/up to 100 recent jobs visible to your account/i)).toBeInTheDocument();
  });

  it("shows unknown health when a health endpoint cannot be observed", async () => {
    mocks.list.mockResolvedValue([]);
    mocks.live.mockRejectedValue(new Error("Unavailable"));
    mocks.ready.mockRejectedValue(new Error("Unavailable"));
    render(<OverviewPage />);

    expect(await screen.findAllByText("Unknown")).toHaveLength(2);
    expect(document.querySelectorAll(".health-dot.unknown")).toHaveLength(2);
  });
});
