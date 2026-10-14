import type { Config } from "tailwindcss";

// Tokens come from styles/tokens.css ("Manuscript" palette, plan §13.2).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        parchment: "var(--color-parchment)",
        cream: "var(--color-cream)",
        maroon: "var(--color-maroon)",
        oxblood: "var(--color-oxblood)",
        gold: "var(--color-gold-leaf)",
        ink: "var(--color-ink)",
        neem: "var(--color-neem)",
        indigo: "var(--color-indigo)",
        sindoor: "var(--color-sindoor)",
        haldi: "var(--color-haldi)",
        clay: "var(--color-clay)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        devanagari: ["var(--font-devanagari-display)"],
        "devanagari-body": ["var(--font-devanagari-body)"],
        sans: ["var(--font-ui)"],
        mono: ["var(--font-mono)"],
      },
    },
  },
  plugins: [],
};
export default config;
