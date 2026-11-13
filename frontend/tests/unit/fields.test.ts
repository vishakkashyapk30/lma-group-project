import { describe, expect, it } from "vitest";
import { fieldEditHint, parseEditText, valueToEditText } from "@/lib/fields";

describe("counsel-facing dossier editors", () => {
  it("formats and parses charge-sheet details without JSON", () => {
    const text = valueToEditText("charge_sheet", { filed: true, date: "2025-02-20" });
    expect(text).toContain("Status: filed");
    expect(text).not.toContain("{");
    expect(parseEditText("charge_sheet", text)).toEqual({ filed: true, date: "2025-02-20" });
  });

  it("accepts readable FIR, bail, co-accused and sections values", () => {
    expect(parseEditText("fir", "Number: 486/2024\nPolice station: PS-2\nDate: 2024-10-19")).toEqual({ number: "486/2024", police_station: "PS-2", date: "2024-10-19" });
    expect(parseEditText("sections", "NDPS 8(C)\nNDPS 21(C)")).toEqual([
      { as_written: "NDPS 8(C)", code: "NDPS", section: "8(C)" },
      { as_written: "NDPS 21(C)", code: "NDPS", section: "21(C)" },
    ]);
    expect(parseEditText("previous_bail", "Sessions Court | 2025-01-15 | rejected")).toEqual([{ court: "Sessions Court", date: "2025-01-15", outcome: "rejected" }]);
    expect(parseEditText("co_accused_bail", "Co-accused-1 | granted | 2025-03-12")).toEqual([{ id: "Co-accused-1", outcome: "granted", date: "2025-03-12" }]);
  });

  it("has plain-language hints and actionable validation", () => {
    expect(fieldEditHint("fir")).not.toMatch(/json/i);
    expect(() => parseEditText("charge_sheet", "{\"filed\": true}")).toThrow(/Status must/);
    expect(() => parseEditText("previous_bail", "{\"court\": \"Sessions\"}")).toThrow(/Court \| YYYY-MM-DD/);
  });
});
