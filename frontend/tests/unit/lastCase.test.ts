import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { clearLastCase, LAST_CASE_KEY, readLastCase, useLastCase, writeLastCase } from "@/lib/lastCase";

afterEach(() => window.localStorage.clear());

describe("last case store", () => {
  it("is empty until a case with a title is written", () => {
    expect(readLastCase()).toBeNull();
    writeLastCase("case-0007", null, null);
    expect(readLastCase()).toBeNull();
  });

  it("round-trips id, title, stage and time", () => {
    writeLastCase("case-0007", "State v. Accused-1", "Draft grounds", new Date("2026-10-27T10:00:00Z"));
    expect(readLastCase()).toEqual({ id: "case-0007", title: "State v. Accused-1", stageLabel: "Draft grounds", at: "2026-10-27T10:00:00.000Z" });
    expect(JSON.parse(window.localStorage.getItem(LAST_CASE_KEY) ?? "{}").id).toBe("case-0007");
  });

  it("ignores malformed or unsafe entries", () => {
    window.localStorage.setItem(LAST_CASE_KEY, "{not json");
    expect(readLastCase()).toBeNull();
    window.localStorage.setItem(LAST_CASE_KEY, JSON.stringify({ id: "../../x?y", title: "T" }));
    expect(readLastCase()).toBeNull();
    window.localStorage.setItem(LAST_CASE_KEY, JSON.stringify({ id: "case-1", title: "" }));
    expect(readLastCase()).toBeNull();
  });

  it("notifies subscribers on write and clear", () => {
    const { result } = renderHook(() => useLastCase());
    expect(result.current).toBeNull();
    act(() => writeLastCase("case-0042", "State v. Accused-9", null));
    expect(result.current?.id).toBe("case-0042");
    act(() => clearLastCase());
    expect(result.current).toBeNull();
  });
});
