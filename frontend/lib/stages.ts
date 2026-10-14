// Workspace stages (plan §13.5): numbered like the Parts of the Constitution. Gates follow Dossier and precede File.
import type { Stage } from "./types";

export const STAGES: { id: Stage; numeral: string; label: string; gate?: "GATE_1_DOSSIER" | "GATE_2_EXPORT" }[] = [
  { id: "INTAKE", numeral: "I", label: "Intake" },
  { id: "DOSSIER", numeral: "II", label: "Dossier", gate: "GATE_1_DOSSIER" },
  { id: "RIGHTS", numeral: "III", label: "Rights" },
  { id: "BRIEF", numeral: "IV", label: "Brief" },
  { id: "SPAR", numeral: "V", label: "Spar" },
  { id: "HEARING_PREP", numeral: "VI", label: "Hearing prep" },
  { id: "FILE", numeral: "VII", label: "File", gate: "GATE_2_EXPORT" },
];
