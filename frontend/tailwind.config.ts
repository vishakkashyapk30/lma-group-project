import type { Config } from "tailwindcss";

// Tokens come from styles/tokens.css (see DESIGN.md). Colours use RGB channel variables so that
// opacity modifiers work (bg-maroon/10, border-gold/40).
const rgb = (name: string) => `rgb(var(--rgb-${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        parchment: { DEFAULT: rgb("parchment"), deep: rgb("parchment-deep") },
        cream: rgb("cream"),
        maroon: { DEFAULT: rgb("maroon"), deep: rgb("maroon-deep") },
        oxblood: rgb("oxblood"),
        gold: { DEFAULT: rgb("gold-leaf"), pale: rgb("gold-pale") },
        "gold-leaf": rgb("gold-leaf"),
        ink: { DEFAULT: rgb("ink"), soft: rgb("ink-soft"), muted: rgb("ink-muted") },
        line: { DEFAULT: rgb("line"), strong: rgb("line-strong") },
        neem: { DEFAULT: rgb("neem"), deep: rgb("neem-deep"), tint: rgb("neem-tint") },
        indigo: { DEFAULT: rgb("indigo"), deep: rgb("indigo-deep"), tint: rgb("indigo-tint"), pale: rgb("indigo-pale") },
        saffron: { DEFAULT: rgb("saffron"), tint: rgb("saffron-tint"), wash: rgb("saffron-wash"), ink: rgb("saffron-ink") },
        sindoor: rgb("sindoor"),
        haldi: rgb("haldi"),
        clay: rgb("clay"),
      },
      fontFamily: {
        display: ["var(--font-display)"],
        serif: ["var(--font-display)"],
        devanagari: ["var(--font-devanagari-display)"],
        "devanagari-body": ["var(--font-devanagari-body)"],
        hindi: ["var(--font-devanagari-body)"],
        sans: ["var(--font-ui)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        "2xs": ["var(--text-2xs)", { lineHeight: "1rem" }],
        xs: ["var(--text-xs)", { lineHeight: "1.125rem" }],
        sm: ["var(--text-sm)", { lineHeight: "1.375rem" }],
        base: ["var(--text-base)", { lineHeight: "1.45rem" }],
        lg: ["var(--text-lg)", { lineHeight: "1.7rem" }],
        xl: ["var(--text-xl)", { lineHeight: "1.85rem" }],
        "2xl": ["var(--text-2xl)", { lineHeight: "2rem" }],
        "3xl": ["var(--text-3xl)", { lineHeight: "2.35rem" }],
        "4xl": ["var(--text-4xl)", { lineHeight: "var(--leading-tight)" }],
        "5xl": ["var(--text-5xl)", { lineHeight: "var(--leading-tight)" }],
        "6xl": ["var(--text-6xl)", { lineHeight: "1.02" }],
        display: ["var(--text-display)", { lineHeight: "0.98", letterSpacing: "var(--tracking-tight)" }],
      },
      lineHeight: {
        devanagari: "var(--leading-devanagari)",
      },
      letterSpacing: {
        caps: "var(--tracking-caps)",
      },
      spacing: {
        nav: "var(--nav-h)",
        rail: "var(--rail-h)",
      },
      maxWidth: {
        content: "var(--content-max)",
        prose: "var(--prose-max)",
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius-md)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        pill: "var(--radius-pill)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow-md)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      transitionDuration: {
        instant: "var(--dur-instant)",
        fast: "var(--dur-fast)",
        base: "var(--dur-base)",
        slow: "var(--dur-slow)",
        deliberate: "var(--dur-deliberate)",
        scene: "var(--dur-scene)",
      },
      transitionTimingFunction: {
        standard: "var(--ease-standard)",
        enter: "var(--ease-enter)",
        exit: "var(--ease-exit)",
        ink: "var(--ease-ink)",
        settle: "var(--ease-settle)",
      },
      zIndex: {
        raised: "10",
        sticky: "30",
        nav: "40",
        drawer: "50",
        modal: "60",
        toast: "70",
        tooltip: "80",
      },
      // Transform and opacity only.
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "fade-out": { from: { opacity: "1" }, to: { opacity: "0" } },
        "rise-in": {
          from: { opacity: "0", transform: "translateY(calc(6px * var(--motion-amplitude)))" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(calc(1 - 0.03 * var(--motion-amplitude)))" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        // Centred dialogs are positioned with translate(-50%, -50%): the animation has to carry it or it would replace it.
        "dialog-in": {
          from: { opacity: "0", transform: "translate(-50%, -50%) scale(calc(1 - 0.03 * var(--motion-amplitude)))" },
          to: { opacity: "1", transform: "translate(-50%, -50%) scale(1)" },
        },
        "slide-in-right": { from: { transform: "translateX(100%)" }, to: { transform: "translateX(0)" } },
        "slide-out-right": { from: { transform: "translateX(0)" }, to: { transform: "translateX(100%)" } },
        "slide-in-left": { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(0)" } },
        "slide-out-left": { from: { transform: "translateX(0)" }, to: { transform: "translateX(-100%)" } },
        "slide-in-up": { from: { transform: "translateY(100%)" }, to: { transform: "translateY(0)" } },
        "breathe": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.6" } },
        "spin-slow": { from: { transform: "rotate(0deg)" }, to: { transform: "rotate(360deg)" } },
        "shimmer": { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-in": "fade-in var(--dur-base) var(--ease) both",
        "fade-out": "fade-out var(--dur-fast) var(--ease) both",
        "rise-in": "rise-in var(--dur-slow) var(--ease) both",
        "scale-in": "scale-in var(--dur-base) var(--ease) both",
        "dialog-in": "dialog-in var(--dur-base) var(--ease) both",
        "slide-in-right": "slide-in-right var(--dur-slow) var(--ease) both",
        "slide-out-right": "slide-out-right var(--dur-base) var(--ease) both",
        "slide-in-left": "slide-in-left var(--dur-slow) var(--ease) both",
        "slide-out-left": "slide-out-left var(--dur-base) var(--ease) both",
        "slide-in-up": "slide-in-up var(--dur-slow) var(--ease) both",
        breathe: "breathe var(--motion-working-loop-max) var(--ease) infinite",
        "spin-slow": "spin-slow 1s linear infinite",
        shimmer: "shimmer 1.4s var(--ease) infinite",
      },
    },
  },
  plugins: [],
};
export default config;
