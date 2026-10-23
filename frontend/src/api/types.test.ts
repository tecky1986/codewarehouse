import { describe, expect, it } from "vitest";
import { isOk } from "./types";

describe("ApiEnvelope", () => {
  it("treats numeric zero as ok", () => {
    expect(isOk({ code: 0, message: "ok", data: { status: "ok" } })).toBe(true);
  });

  it("treats non-zero code as not ok", () => {
    expect(isOk({ code: "E_ENGINE", message: "fail", data: null })).toBe(false);
  });
});
