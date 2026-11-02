import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PageSkeleton } from "@/components/common/PageSkeleton";

describe("PageSkeleton", () => {
  for (const kind of ["list", "board", "library"] as const) {
    it(`${kind}: a labelled status that waits 150 ms before it shows, in the page's own container`, () => {
      render(<PageSkeleton kind={kind} label="Loading the page" />);
      const s = screen.getByRole("status", { name: "Loading the page" });
      expect(s.className).toContain("skeleton-delayed");
      expect(s.className).toContain("max-w-content");
      expect(s.querySelectorAll("[aria-hidden=true]").length).toBeGreaterThan(3);
    });
  }
});
