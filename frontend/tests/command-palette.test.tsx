import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CommandPalette } from "@/components/navigation/command-palette";
import { takePendingJobSearch } from "@/lib/navigation/pending-search";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));
vi.mock("@/components/auth/auth-provider", () => ({
  useAuth: () => ({ user: { roles: ["USER"] }, signOut: vi.fn() }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ show: vi.fn() }),
}));

describe("command palette", () => {
  it("searches jobs and supports arrow/enter navigation and Escape", () => {
    const close = vi.fn();
    const onSearch = vi.fn();
    window.addEventListener("aetherflow:job-search", onSearch);
    render(<CommandPalette open onClose={close} />);
    const input = screen.getByRole("textbox", { name: "Search commands" });
    fireEvent.change(input, { target: { value: "batch-42" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/jobs");
    expect(onSearch).toHaveBeenCalledOnce();
    expect(takePendingJobSearch()).toBe("batch-42");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(close).toHaveBeenCalled();
    window.removeEventListener("aetherflow:job-search", onSearch);
  });
});
