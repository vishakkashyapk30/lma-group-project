// Own SVG line art: Nyay ki Devi in the manuscript's line style (plan §13.2). A classical standing figure with a blindfold,
// a sword and scales; the sword can morph into a bound Constitution (the 2024 statue's idea, drawn by us, not copied).
// Every part is a separately addressable layer (data-layer) so GSAP can DrawSVG the lines and MorphSVG blade -> cover.
// Static props describe the final frame: eyes open, no blindfold, the book held. Decorative: aria-hidden unless `title`.
import type { CSSProperties, ReactElement, Ref } from "react";
import { TONE_COLOR, type ArtTone } from "./tone";

export const LADY_JUSTICE_LAYERS = [
  "figure",
  "blindfold",
  "eyes",
  "sword",
  "book",
  "scale-left",
  "scale-right",
  "beam",
] as const;
export type LadyJusticeLayer = (typeof LADY_JUSTICE_LAYERS)[number];

export interface LadyJusticeProps {
  className?: string;
  /** Ref to the root <svg> (query `[data-layer="..."]` inside it). */
  svgRef?: Ref<SVGSVGElement>;
  /** Line colour for all layers. Default gold (on oxblood). */
  tone?: ArtTone;
  /** Static state: blindfold on (eyes hidden) or dissolved (eyes open). Default false. */
  blindfold?: boolean;
  /** Static state: what the right hand holds. Default "book". */
  held?: "sword" | "book";
  /** Stroke width in viewBox units. */
  strokeWidth?: number;
  /** Per-layer colour overrides, e.g. maroon scales where they break out over cream. */
  layerColors?: Partial<Record<LadyJusticeLayer, string>>;
  /** Accessible name; when omitted the art is aria-hidden. */
  title?: string;
}

const HALO_TICKS = Array.from({ length: 24 }, (_, i) => {
  const a = (i * 15 * Math.PI) / 180;
  const f = (r: number) => [(200 + r * Math.cos(a)).toFixed(2), (106 + r * Math.sin(a)).toFixed(2)] as const;
  const [x1, y1] = f(60);
  const [x2, y2] = f(i % 2 === 0 ? 70 : 66);
  return `M${x1} ${y1}L${x2} ${y2}`;
}).join("");

export function LadyJustice({
  className,
  svgRef,
  tone = "gold",
  blindfold = false,
  held = "book",
  strokeWidth = 1.6,
  layerColors,
  title,
}: LadyJusticeProps): ReactElement {
  const layerStyle = (l: LadyJusticeLayer, extra?: CSSProperties): CSSProperties => ({
    ...(layerColors?.[l] ? { color: layerColors[l] } : null),
    ...extra,
  });
  return (
    <svg
      ref={svgRef}
      viewBox="-24 0 424 650"
      className={className}
      style={{ color: TONE_COLOR[tone], overflow: "visible" }}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {/* Figure: halo, head, robe, arms, plinth */}
      <g data-layer="figure" style={layerStyle("figure")}>
        <path data-part="wash" d="M176 158C160 190 162 250 152 330C142 420 130 520 112 604C160 614 240 614 288 604C270 520 258 420 248 330C238 250 240 190 224 158Z" fill="currentColor" fillOpacity="0.07" stroke="none" />
        <circle data-part="halo" cx="200" cy="106" r="54" />
        <path data-part="halo-ticks" d={HALO_TICKS} strokeWidth={strokeWidth * 0.75} />
        {/* hair and bun */}
        <path d="M174 104C168 78 182 64 200 64C218 64 232 78 226 104" />
        <path d="M192 64C190 50 210 46 212 58C213 64 206 66 200 64" />
        <path d="M176 108C172 124 178 134 186 138M224 108C228 124 222 134 214 138" />
        <path d="M184 76C192 70 208 70 216 76" strokeWidth={strokeWidth * 0.7} />
        {/* face */}
        <path d="M176 100C176 128 188 140 200 140C212 140 224 128 224 100" />
        <path d="M200 110L197 121Q200 123 203 121" strokeWidth={strokeWidth * 0.8} />
        <path d="M194 129Q200 133 206 129" strokeWidth={strokeWidth * 0.8} />
        <path d="M181 98Q190 93 198 98M202 98Q210 93 219 98" strokeWidth={strokeWidth * 0.8} />
        {/* neck and neckline */}
        <path d="M190 138V152M210 138V152M190 152L200 178L210 152" />
        {/* robe */}
        <path d="M176 158C160 190 162 250 152 330C142 420 130 520 112 604" />
        <path d="M224 158C240 190 238 250 248 330C258 420 270 520 288 604" />
        <path d="M112 604C160 614 240 614 288 604" />
        <path d="M176 160C200 200 232 232 244 292" />
        <path d="M168 262C190 276 210 276 232 262M166 274C190 290 210 290 234 274" />
        <path d="M180 292C174 400 164 500 150 600M200 296C200 400 202 500 204 610M222 292C232 400 242 500 256 600" strokeWidth={strokeWidth * 0.8} />
        <path d="M190 302C186 380 178 460 176 560M212 302C214 380 222 460 226 560" strokeWidth={strokeWidth * 0.6} />
        {/* left arm raised to the scales, right arm to the sword/book */}
        <path d="M176 158C146 168 120 196 98 226M168 198C146 218 124 240 100 250" />
        <path d="M70 232C70 224 98 224 98 232V248C98 256 70 256 70 248Z" />
        <path d="M224 158C250 172 272 206 286 244M232 200C252 222 270 248 288 272" />
        <path d="M284 254C284 246 312 246 312 254V272C312 280 284 280 284 272Z" />
        {/* plinth */}
        <path d="M96 616H304V632H96ZM84 632H316V646H84Z" />
      </g>

      {/* Scales: beam, then two pans that fall away in the transition */}
      <g data-layer="beam" style={layerStyle("beam")}>
        <path d="M22 128H146M84 112V240" />
        <circle cx="84" cy="106" r="6" />
        <circle cx="22" cy="128" r="3.5" />
        <circle cx="146" cy="128" r="3.5" />
      </g>
      <g data-layer="scale-left" style={layerStyle("scale-left")}>
        <path d="M22 128L-2 192M22 128L46 192M22 128V192" strokeWidth={strokeWidth * 0.7} />
        <path d="M-6 192H50C48 212 -4 212 -6 192Z" />
      </g>
      <g data-layer="scale-right" style={layerStyle("scale-right")}>
        <path d="M146 128L120 192M146 128L172 192M146 128V192" strokeWidth={strokeWidth * 0.7} />
        <path d="M118 192H174C172 212 120 212 118 192Z" />
      </g>

      {/* Sword (blade morphs into the book cover) */}
      <g data-layer="sword" style={layerStyle("sword", { opacity: held === "sword" ? 1 : 0 })}>
        <path data-part="blade" d="M298 56L306 100V238H290V100Z" />
        <g data-part="hilt">
          <path d="M274 242H322M274 242Q270 236 276 234M322 242Q326 236 320 234M298 280V294" />
          <circle cx="298" cy="300" r="5" />
        </g>
        <path data-part="fuller" d="M298 84V228" strokeWidth={strokeWidth * 0.6} />
      </g>

      {/* Bound Constitution (cover is the MorphSVG target; details fade in) */}
      <g data-layer="book" style={layerStyle("book", { opacity: held === "book" ? 1 : 0 })}>
        <path data-part="cover" d="M266 146Q301 136 336 146V262Q301 252 266 262Z" />
        <g data-part="details">
          <path d="M278 143V258M266 176Q301 170 336 176M266 232Q301 226 336 232" strokeWidth={strokeWidth * 0.8} />
          <circle cx="309" cy="204" r="12" strokeWidth={strokeWidth * 0.8} />
          <path d="M309 192V216M297 204H321M300.5 195.5L317.5 212.5M317.5 195.5L300.5 212.5" strokeWidth={strokeWidth * 0.5} />
          <path d="M292 160H326M296 244H322" strokeWidth={strokeWidth * 0.6} />
          <path d="M324 258V280L328 276L332 280V256" strokeWidth={strokeWidth * 0.8} />
        </g>
      </g>

      {/* Eyes (open) and blindfold (dissolves) */}
      <g data-layer="eyes" style={layerStyle("eyes", { opacity: blindfold ? 0 : 1 })}>
        <path d="M182 107Q190 100 198 107Q190 113 182 107ZM202 107Q210 100 218 107Q210 113 202 107Z" strokeWidth={strokeWidth * 0.8} />
        <circle cx="190" cy="107" r="2.3" fill="currentColor" stroke="none" />
        <circle cx="210" cy="107" r="2.3" fill="currentColor" stroke="none" />
      </g>
      <g data-layer="blindfold" style={layerStyle("blindfold", { opacity: blindfold ? 1 : 0 })}>
        <path d="M172 98Q200 94 228 98V114Q200 110 172 114Z" fill="currentColor" fillOpacity="0.14" />
        <path d="M180 106H220" strokeWidth={strokeWidth * 0.6} />
        <path d="M228 104C244 100 254 110 252 126M228 110C240 112 244 126 238 140" />
        <circle cx="229" cy="106" r="4" />
      </g>
    </svg>
  );
}

export default LadyJustice;
