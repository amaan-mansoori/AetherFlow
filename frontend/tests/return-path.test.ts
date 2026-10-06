import { describe, expect, it } from "vitest";
import { safeReturnPath } from "@/lib/auth/return-path";

describe("safeReturnPath", () => {
  it("preserves same-origin application paths and their query/hash", () => {
    expect(safeReturnPath("/jobs?state=FAILED#recent")).toBe("/jobs?state=FAILED#recent");
  });

  it.each([
    null,
    "",
    "https://attacker.example/",
    "//attacker.example/",
    "/\\attacker.example/",
  ])("rejects unsafe or absent return destinations: %s", (value) => {
    expect(safeReturnPath(value)).toBeNull();
  });
});
