// Shared colour tones for the landing line art. Values are the Manuscript tokens (styles/tokens.css).
export type ArtTone = "gold" | "gold-pale" | "maroon" | "oxblood" | "ink" | "cream";

export const TONE_COLOR: Record<ArtTone, string> = {
  gold: "var(--color-gold-leaf)",
  "gold-pale": "var(--color-gold-pale)",
  maroon: "var(--color-maroon)",
  oxblood: "var(--color-oxblood)",
  ink: "var(--color-ink)",
  cream: "var(--color-cream)",
};
