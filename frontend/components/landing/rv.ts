import type { CSSProperties } from "react";

/** Stagger index for a band's reveal (styles/landing.css, `[data-rv]`). */
export const rv = (i: number) => ({ "--i": i }) as CSSProperties;
