import { describe, expect, it } from "vitest";
import { MOCK_RIGHTS } from "@/lib/mock/case0007";
import { addDays, dateAt, diffDays, fraction, stateAt, timelineFromReport } from "@/lib/rightsTimeline";

const tl = timelineFromReport(MOCK_RIGHTS, false)!;

describe("rights timeline on the sample case", () => {
  it("reads the Rights Radar's own dates", () => {
    expect(tl).toMatchObject({ arrest: "2024-08-20", firstRemand: "2024-08-21", limitEnd: "2024-10-19", limitDays: 60, chargeSheet: "2024-11-02", oneThird: "2026-12-20", oneHalf: "2028-02-19" });
  });

  it("matches the dossier's 167 days in custody on the as-of date", () => {
    expect(stateAt(tl, tl.asOf).custodyDays).toBe(167);
  });

  it("the thresholds are 852 and 1,278 days from the arrest, as the Radar says", () => {
    expect(diffDays(tl.arrest, tl.oneThird!)).toBe(852);
    expect(diffDays(tl.arrest, tl.oneHalf!)).toBe(1278);
  });

  it("default bail: closed by the charge sheet on day 74, open on days 61 to 73", () => {
    const s = stateAt(tl, "2025-02-18").defaultBail;
    expect(s.word).toBe("Closed");
    expect(s.sentence).toContain("day 74");
    expect(s.sentence).toContain("days 61 to 73");
    expect(stateAt(tl, "2024-10-01").defaultBail.word).toBe("Not yet");
    // Between the window opening and the charge sheet the Radar did not say ELIGIBLE, so the timeline says Check.
    expect(stateAt(tl, "2024-10-25").defaultBail.word).toBe("Check");
  });

  it("undertrial limit: never more than Check while antecedents are unknown", () => {
    expect(stateAt(tl, "2025-02-18").undertrial.word).toBe("Not yet");
    const mid = stateAt(tl, "2027-06-01").undertrial;
    expect(mid.word).toBe("Check");
    expect(mid.sentence).toContain("do not say");
    expect(stateAt(tl, "2028-03-01").undertrial.word).toBe("Check");
  });

  it("no state of the sample ever reads Open", () => {
    for (let d = tl.arrest; d < "2028-06-01"; d = addDays(d, 9)) {
      const s = stateAt(tl, d);
      expect(s.defaultBail.word).not.toBe("Open");
      expect(s.undertrial.word).not.toBe("Open");
    }
  });

  it("a missing charge-sheet date keeps default bail at Check after the limit", () => {
    const s = stateAt({ ...tl, chargeSheet: null, defaultStatus: "CHECK" }, "2024-11-15").defaultBail;
    expect(s.word).toBe("Check");
    expect(s.sentence).toContain("do not give a charge-sheet date");
  });

  it("a charge sheet within the limit means default bail does not apply", () => {
    expect(stateAt({ ...tl, chargeSheet: "2024-10-01" }, "2025-01-01").defaultBail.word).toBe("Does not apply");
  });

  it("fraction and dateAt are inverse to the day", () => {
    const start = "2024-08-20";
    const end = "2028-06-01";
    for (const d of ["2024-08-20", "2025-02-18", "2026-12-20", "2028-06-01"]) expect(dateAt(fraction(d, start, end), start, end)).toBe(d);
    expect(fraction("2020-01-01", start, end)).toBe(0);
    expect(fraction("2030-01-01", start, end)).toBe(1);
  });
});

describe("a report without dates (as the API may send it)", () => {
  const bare = { ...MOCK_RIGHTS, checks: MOCK_RIGHTS.checks.map((c) => ({ ...c, dates: undefined })) };
  it("falls back to the dossier's dates and the Radar's own day counts", () => {
    const x = timelineFromReport(bare as typeof MOCK_RIGHTS, false, { arrest: "2024-08-20", firstRemand: "2024-08-21", chargeSheet: "2024-11-02" })!;
    expect(x.limitDays).toBe(60);
    expect(x.limitEnd).toBe("2024-10-19");
    expect(x.oneThird).toBe("2026-12-20");
    expect(x.oneHalf).toBe("2028-02-19");
    expect(stateAt(x, "2025-02-18").defaultBail.word).toBe("Closed");
  });
  it("without an arrest date there is no timeline", () => {
    expect(timelineFromReport(bare as typeof MOCK_RIGHTS, false, {})).toBeNull();
  });
});
