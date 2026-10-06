import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import DemoPage from "@/app/demo/page";

const { demoStatus } = vi.hoisted(() => ({ demoStatus: vi.fn() }));

vi.mock("@/lib/api/client", () => ({ api: { demoStatus } }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("demo access page", () => {
  beforeEach(() => demoStatus.mockReset());

  it("explains when the operator has not provisioned demo access", async () => {
    demoStatus.mockResolvedValue({ available: false, access_mode: "read-only" });
    render(<DemoPage />);

    expect(await screen.findByText(/Demo access is unavailable\. The operator has not enabled/))
      .toBeInTheDocument();
    expect(screen.queryByText("recruiter-demo@example.com")).not.toBeInTheDocument();
  });

  it("labels the demo read-only and does not expose credentials or execution controls", async () => {
    demoStatus.mockResolvedValue({ available: true, access_mode: "read-only" });
    render(<DemoPage />);

    expect(await screen.findByText("recruiter-demo@example.com")).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
    expect(screen.getByText(/password supplied by the environment operator/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit|cancel/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /continue to sign in/i })).toHaveAttribute("href", "/login");
  });
});
