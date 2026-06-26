// Severity palette and the color-blind-safe redundant encodings (06 §6.2/§6.7).
// Color is NEVER the only channel: every severity also differs in border weight, line dash,
// motion (DANGER pulses), and a text glyph + ARIA-ish label, so the state reads without hue.

import type { Severity } from "./types";

export interface SeverityStyle {
  fill: string;
  stroke: string;
  lineWidth: number;
  /** canvas line dash; [] = solid. UNKNOWN is dashed + hatched. */
  dash: number[];
  /** redundant non-color glyph drawn on the icon/zone (color-blind safe). */
  glyph: string;
  /** DANGER pulses; others are static. */
  pulse: boolean;
  /** UNKNOWN gets a diagonal hatch fill over the polygon. */
  hatch: boolean;
  /** banner / text accent color. */
  accent: string;
}

export const SEVERITY: Record<Severity, SeverityStyle> = {
  SAFE: {
    fill: "rgba(70,84,102,0.20)", stroke: "rgba(150,164,184,0.30)", lineWidth: 1,
    dash: [], glyph: "", pulse: false, hatch: false, accent: "#8a94a4",
  },
  CAUTION: {
    fill: "rgba(240,170,40,0.46)", stroke: "#f0aa28", lineWidth: 2.5,
    dash: [], glyph: "!", pulse: false, hatch: false, accent: "#f6b73c",
  },
  DANGER: {
    fill: "rgba(225,60,55,0.74)", stroke: "#ff4a3d", lineWidth: 3.5,
    dash: [], glyph: "‼", pulse: true, hatch: false, accent: "#ff5a4d",
  },
  UNKNOWN: {
    fill: "rgba(120,124,134,0.26)", stroke: "rgba(190,196,206,0.65)", lineWidth: 2,
    dash: [7, 5], glyph: "?", pulse: false, hatch: true, accent: "#b9bfc9",
  },
};

export const THEME = {
  bg: "#0b0e13",
  panel: "#0e131b",
  truckFill: "rgba(38,46,58,0.96)",
  truckStroke: "#5b6675",
  text: "#cdd6e0",
  textDim: "#8a94a4",
  pipLive: "#39d98a",
  pipLost: "#ff4a3d",
  pipWarming: "#f6b73c",
};
