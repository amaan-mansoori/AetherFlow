import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import RegisterPage from "@/app/register/page";
import type { User } from "@/types/api";

const { register } = vi.hoisted(() => ({ register: vi.fn() }));

vi.mock("@/lib/api/client", () => ({ api: { register } }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const user: User = {
  id: "user-1",
  email: "new-user@example.com",
  roles: ["USER"],
  created_at: "2026-10-04T10:00:00Z",
  last_login_at: null,
};

describe("registration page", () => {
  beforeEach(() => register.mockReset());

  it("creates a standard account and leaves sign-in as a separate step", async () => {
    register.mockResolvedValue(user);
    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: " new-user@example.com " },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a long registration password" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "a long registration password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("heading", { name: "You're registered" })).toBeInTheDocument();
    expect(register).toHaveBeenCalledWith("new-user@example.com", "a long registration password");
    expect(screen.getByRole("link", { name: /continue to sign in/i })).toHaveAttribute("href", "/login");
  });

  it("rejects mismatched passwords without sending the request", async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "new-user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a long registration password" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "a different password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The passwords do not match.");
    expect(register).not.toHaveBeenCalled();
  });
});
