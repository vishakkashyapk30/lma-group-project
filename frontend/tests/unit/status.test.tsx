/**
 * Status presentation (plan §13.2): each status ALWAYS shows an icon and a label, never colour alone.
 * Plan table groupings are asserted exactly; the Rights Radar / spar / claim statuses that the plan lists in other
 * sections (§7.3, §9, §10) get colours by the ASSUMPTIONs below.
 */
import fs from "node:fs";
import path from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { STATUS_META } from "@/lib/status";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FRONTEND_ROOT, tsUnion } from "./_helpers";

const tokens = fs.readFileSync(path.join(FRONTEND_ROOT, "styles/tokens.css"), "utf8");
const NEEM = "--color-neem", INDIGO = "--color-indigo", SINDOOR = "--color-sindoor", HALDI = "--color-haldi", CLAY = "--color-clay";

// Plan §13.2 status table (exact).
const PLAN_TABLE: [string, string, string][] = [
  ["VERIFIED", NEEM, "✔"], ["SUPPORTED", NEEM, "✔"], ["OK", NEEM, "✔"],
  ["COMPUTED", INDIGO, "ƒ"],
  ["UNSUPPORTED", SINDOOR, "✖"], ["UNANSWERED", SINDOOR, "✖"], ["FLAG", SINDOOR, "✖"],
  ["AMBIGUOUS", HALDI, "?"], ["CHECK", HALDI, "?"], ["NEEDS_REVIEW", HALDI, "?"], ["UNKNOWN", HALDI, "?"],
  ["USER_STATED", CLAY, "✎"], ["USER_EDITED", CLAY, "✎"],
];

// ASSUMPTION: colours for statuses the plan table does not list. Allowed colour families per status.
const ASSUMED_COLOURS: [string, string[]][] = [
  ["ELIGIBLE", [NEEM, INDIGO]], ["ANSWERED", [NEEM, INDIGO]], ["REPAIRED", [NEEM, INDIGO]],
  ["WINDOW_CLOSED", [SINDOOR]], ["BAR_APPLIES", [SINDOOR]],
  ["NOT_YET", [HALDI]], ["PARTLY", [HALDI]], ["STALE", [HALDI]],
  ["NOT_APPLICABLE", [CLAY]], ["A", [CLAY]], ["B", [CLAY]], ["C", [CLAY]], ["D", [CLAY]], // neutral family
  ["CURRENT", [NEEM, INDIGO, CLAY]], // a claim that is not stale
  // ASSUMPTION: good-law badges in the library (plan §13.5 "citation graph with good-law badges"); OK/UNKNOWN already covered.
  ["OVERRULED", [SINDOOR]], ["DISTINGUISHED", [HALDI]],
];

const ALL_STATUSES = [...PLAN_TABLE.map((r) => r[0]), ...ASSUMED_COLOURS.map((r) => r[0])];
const RESERVED_ICON_OWNER: Record<string, string[]> = { "ƒ": ["COMPUTED"], "✎": ["USER_STATED", "USER_EDITED"] };

describe("STATUS_META: plan §13.2 table, exact groupings", () => {
  it.each(PLAN_TABLE)("%s -> %s with icon %s", (status, colorVar, icon) => {
    expect(STATUS_META[status]).toBeDefined();
    expect(STATUS_META[status].colorVar).toBe(colorVar);
    expect(STATUS_META[status].icon).toBe(icon);
  });
});

describe("STATUS_META: every status has an icon, a label and a colour (never colour alone)", () => {
  it.each(ALL_STATUSES)("%s has non-empty icon, label and colorVar", (status) => {
    const meta = STATUS_META[status];
    expect(meta, `STATUS_META is missing ${status}`).toBeDefined();
    expect(meta.icon.trim()).not.toBe("");
    expect(meta.label.trim()).not.toBe("");
    expect(meta.colorVar.trim()).not.toBe("");
  });

  it.each(ASSUMED_COLOURS)("%s uses an allowed colour family (ASSUMPTION)", (status, families) => {
    expect(STATUS_META[status], `STATUS_META is missing ${status}`).toBeDefined();
    expect(families).toContain(STATUS_META[status].colorVar);
  });

  it("every colorVar is declared in tokens.css", () => {
    for (const [status, meta] of Object.entries(STATUS_META)) {
      expect(tokens, `${status} -> ${meta.colorVar}`).toMatch(new RegExp(`${meta.colorVar}\\s*:\\s*#[0-9A-Fa-f]{6}`));
    }
  });

  it("only status colours (neem, indigo, sindoor, haldi, clay) are used for statuses, never gold", () => {
    for (const meta of Object.values(STATUS_META)) {
      expect([NEEM, INDIGO, SINDOOR, HALDI, CLAY]).toContain(meta.colorVar);
    }
  });

  it("labels are unique per status (distinct meanings are distinguishable by text)", () => {
    const entries = ALL_STATUSES.filter((s) => STATUS_META[s]).map((s) => [s, STATUS_META[s].label.toLowerCase()] as const);
    const seen = new Map<string, string>();
    for (const [status, label] of entries) {
      expect(seen.get(label), `label "${label}" shared by ${seen.get(label)} and ${status}`).toBeUndefined();
      seen.set(label, status);
    }
  });

  // RECONCILED: the redesign speaks to counsel in plain words (workspace-redesign handoff: "Plain-language status labels"), so the
  // labels are "Entered by you" and "Corrected by you"; they must still differ, which is what this test protects.
  it("USER_STATED and USER_EDITED stay distinguishable by label ('Entered by you' vs 'Corrected by you')", () => {
    expect(STATUS_META.USER_STATED.label).toBe("Entered by you");
    expect(STATUS_META.USER_EDITED.label).toBe("Corrected by you");
  });

  it("the f and pencil icons are reserved: ƒ only for COMPUTED, ✎ only for USER_*", () => {
    for (const status of ALL_STATUSES) {
      const icon = STATUS_META[status]?.icon;
      for (const [reserved, owners] of Object.entries(RESERVED_ICON_OWNER)) {
        if (icon === reserved) expect(owners).toContain(status);
      }
    }
  });

  it("an icon never appears with two different colours (icon implies colour family)", () => {
    const byIcon = new Map<string, Set<string>>();
    for (const status of ALL_STATUSES) {
      const m = STATUS_META[status];
      if (!m) continue;
      byIcon.set(m.icon, (byIcon.get(m.icon) ?? new Set()).add(m.colorVar));
    }
    for (const [icon, colours] of byIcon) expect(colours.size, `icon ${icon}`).toBe(1);
  });

  it("A, B, C, D (Antil categories) have four distinct labels", () => {
    const labels = ["A", "B", "C", "D"].map((s) => STATUS_META[s]?.label);
    expect(new Set(labels).size).toBe(4);
  });
});

describe("STATUS_META covers every status union in lib/types.ts", () => {
  it.each(["FieldStatus", "RightsStatus", "ClaimCheck", "SparringVerdict", "ClaimState", "GoodLawStatus"])(
    "%s members all have a STATUS_META entry",
    (union) => {
      for (const member of tsUnion(union)) {
        expect(STATUS_META[member], `${union}.${member} missing from STATUS_META`).toBeDefined();
      }
    },
  );
  it("has no entry outside the known status vocabulary (no stray keys)", () => {
    for (const key of Object.keys(STATUS_META)) expect(ALL_STATUSES).toContain(key);
  });
});

describe("<StatusBadge /> (fails until implemented)", () => {
  it.each(PLAN_TABLE)("%s renders its icon AND its label as text, not only a colour class", (status, _c, icon) => {
    const { container } = render(<StatusBadge status={status} />);
    const text = container.textContent ?? "";
    expect(text).toContain(icon);
    expect(text).toContain(STATUS_META[status].label);
  });

  // RECONCILED: plain-language label (workspace-redesign handoff): UNSUPPORTED reads "Not found"; the raw enum stays in data-status.
  it("UNSUPPORTED shows the cross icon and the words 'Not found'", () => {
    const { getByTestId } = render(<StatusBadge status="UNSUPPORTED" />);
    const badge = getByTestId("status-badge");
    expect(badge).toHaveTextContent("✖");
    expect(badge).toHaveTextContent("Not found");
    expect(badge).toHaveAttribute("data-status", "UNSUPPORTED");
  });

  it("the label is real text in the accessibility tree; the icon glyph is decorative (aria-hidden) (ASSUMPTION)", () => {
    const { container } = render(<StatusBadge status="NEEDS_REVIEW" />);
    const hidden = container.querySelector("[aria-hidden='true']");
    expect(hidden?.textContent).toBe("?");
    expect(container.textContent).toContain("Needs your review"); // RECONCILED: plain-language label (was "Needs review")
  });

  it("exposes the raw status in data-status and references its colour token (ASSUMPTION)", () => {
    const { getByTestId } = render(<StatusBadge status="COMPUTED" />);
    const badge = getByTestId("status-badge");
    expect(badge).toHaveAttribute("data-status", "COMPUTED");
    const html = badge.outerHTML;
    expect(html.includes("--color-indigo") || /indigo/.test(html)).toBe(true);
  });

  it("merges a className prop onto the badge", () => {
    const { getByTestId } = render(<StatusBadge status="OK" className="extra-x" />);
    expect(getByTestId("status-badge")).toHaveClass("extra-x");
  });

  it("an unknown status still renders non-empty text rather than a bare colour (ASSUMPTION)", () => {
    const { container } = render(<StatusBadge status="SOMETHING_NEW" />);
    expect((container.textContent ?? "").trim().length).toBeGreaterThan(0);
  });
});
