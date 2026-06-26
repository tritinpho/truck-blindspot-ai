// Severity palette and the color-blind-safe redundant encodings (06 §6.2/§6.7).
// Color is NEVER the only channel: every severity also differs in border weight, line dash,
// motion (DANGER pulses), and a text glyph + ARIA-ish label, so the state reads without hue.
//
// Day/night (S6 polish): the cabin display must be readable in daylight and not blinding at night.
// `THEME` (canvas chrome) and the COLOR fields of `SEVERITY` are swapped in place by applyTheme();
// scene.ts / ui.ts read them live every frame, so a switch needs no other change. The STRUCTURAL
// fields (lineWidth, dash, glyph, pulse, hatch) are theme-independent — the safety semantics and the
// color-blind-safe channels are identical in both themes.

import type { Severity, ThemeMode } from "./types";

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

// Live objects (mutated by applyTheme). Initial values = night, so the default look is unchanged.
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
  hatch: "rgba(200,206,216,0.30)",   // UNKNOWN hatch lines (legible on the panel)
  blobFill: "rgba(14,19,27,0.92)",   // object-blob centre (contrasts with the panel)
};

// --- palettes (only the fields that differ between themes) ---

type SeverityColors = Pick<SeverityStyle, "fill" | "stroke" | "accent">;

interface Palette {
  theme: typeof THEME;
  severity: Record<Severity, SeverityColors>;
}

const NIGHT: Palette = {
  theme: { ...THEME },
  severity: {
    SAFE: { fill: SEVERITY.SAFE.fill, stroke: SEVERITY.SAFE.stroke, accent: SEVERITY.SAFE.accent },
    CAUTION: { fill: SEVERITY.CAUTION.fill, stroke: SEVERITY.CAUTION.stroke, accent: SEVERITY.CAUTION.accent },
    DANGER: { fill: SEVERITY.DANGER.fill, stroke: SEVERITY.DANGER.stroke, accent: SEVERITY.DANGER.accent },
    UNKNOWN: { fill: SEVERITY.UNKNOWN.fill, stroke: SEVERITY.UNKNOWN.stroke, accent: SEVERITY.UNKNOWN.accent },
  },
};

const DAY: Palette = {
  theme: {
    bg: "#e9edf2",
    panel: "#dde3ea",
    truckFill: "rgba(188,197,210,0.96)",
    truckStroke: "#7c8696",
    text: "#1c2530",
    textDim: "#566273",
    pipLive: "#1f9d5e",
    pipLost: "#d62a1e",
    pipWarming: "#b4790a",
    hatch: "rgba(60,70,84,0.42)",     // dark hatch reads on a light panel
    blobFill: "rgba(26,34,45,0.92)",  // dark blob contrasts on a light panel
  },
  severity: {
    SAFE: { fill: "rgba(120,135,155,0.22)", stroke: "rgba(92,106,126,0.55)", accent: "#566273" },
    CAUTION: { fill: "rgba(238,158,18,0.44)", stroke: "#c2800a", accent: "#8a5800" },
    DANGER: { fill: "rgba(222,46,36,0.52)", stroke: "#cc1d12", accent: "#a81409" },
    UNKNOWN: { fill: "rgba(110,118,130,0.26)", stroke: "rgba(70,80,94,0.70)", accent: "#465264" },
  },
};

const PALETTES: Record<"night" | "day", Palette> = { night: NIGHT, day: DAY };
const STORE_KEY = "bsw.theme";

/** Resolve `auto` to a concrete theme by time of day (kept in sync with the inline head script). */
export function resolveTheme(mode: ThemeMode): "night" | "day" {
  if (mode === "day" || mode === "night") return mode;
  const h = new Date().getHours();
  return h >= 6 && h < 18 ? "day" : "night";
}

/** Swap the live THEME + SEVERITY colors, set the DOM `data-theme`, and persist the mode. */
export function applyTheme(mode: ThemeMode): "night" | "day" {
  const resolved = resolveTheme(mode);
  const p = PALETTES[resolved];
  Object.assign(THEME, p.theme);
  for (const sev of Object.keys(p.severity) as Severity[]) {
    Object.assign(SEVERITY[sev], p.severity[sev]);
  }
  document.documentElement.dataset.theme = resolved;
  try {
    localStorage.setItem(STORE_KEY, mode);
  } catch {
    /* private mode / storage off — theme still applies for this session */
  }
  return resolved;
}

export function getThemeMode(): ThemeMode {
  try {
    const m = localStorage.getItem(STORE_KEY);
    if (m === "day" || m === "night" || m === "auto") return m;
  } catch {
    /* ignore */
  }
  return "auto";
}

/** Apply the persisted (or auto) theme at startup. Returns the stored mode for the settings UI. */
export function initTheme(): ThemeMode {
  const mode = getThemeMode();
  applyTheme(mode);
  return mode;
}
