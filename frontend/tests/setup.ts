import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { api } from "@/lib/api/client";

afterEach(() => {
  cleanup();
  api.clearSession();
  vi.unstubAllGlobals();
});
