// Canvas scene: the config-driven top-view truck, 8 zones tinted by severity, generic object
// blobs at zone centroids, and per-zone range readouts (FR-05/06, 06 §6.1/§6.2).
//
// Severity reads WITHOUT color (06 §6.2): fill + border weight + dash + DANGER pulse + a glyph.
// During SIGNAL_LOST the whole map is forced to UNKNOWN (hatched) by the caller's phase.

import type { SceneConfig, ZoneCfg } from "./config";
import type { Severity, SystemPhase, ZoneState } from "./types";
import { SEVERITY, THEME } from "./theme";
import { zoneName } from "./i18n";

export interface RenderParams {
  states: Map<string, ZoneState>;
  phase: SystemPhase;
  localEnabled: Map<string, boolean>;
  animMs: number;
}

export class Scene {
  readonly canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private cfg: SceneConfig;

  constructor(canvas: HTMLCanvasElement, cfg: SceneConfig) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d")!;
    this.cfg = cfg;
  }

  /** Size the backing store to the container (DPR-aware) and return the CSS size. */
  fit(): void {
    const parent = this.canvas.parentElement;
    const avail = parent ? Math.min(parent.clientWidth, parent.clientHeight) : 360;
    const cssSize = Math.max(280, avail - 8);
    const dpr = window.devicePixelRatio || 1;
    this.canvas.style.width = `${cssSize}px`;
    this.canvas.style.height = `${cssSize}px`;
    this.canvas.width = Math.round(cssSize * dpr);
    this.canvas.height = Math.round(cssSize * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  private get size(): number {
    return this.canvas.width / (window.devicePixelRatio || 1);
  }

  private effectiveSeverity(z: ZoneCfg, p: RenderParams): Severity {
    if (p.phase === "SIGNAL_LOST") return "UNKNOWN";
    const st = p.states.get(z.id);
    return st ? st.severity : "UNKNOWN";
  }

  render(p: RenderParams): void {
    const ctx = this.ctx;
    const S = this.size;
    ctx.clearRect(0, 0, S, S);
    ctx.fillStyle = THEME.panel;
    ctx.fillRect(0, 0, S, S);

    // zones first (under the truck body)
    for (const z of this.cfg.zones) {
      const enabled = (p.localEnabled.get(z.id) ?? true) && z.enabled;
      if (!enabled) { this.drawDisabledZone(z, S); continue; }
      this.drawZone(z, this.effectiveSeverity(z, p), p, S);
    }

    this.drawTruck(S);
    this.drawOrientation(S);

    // icons on top so they're never occluded by neighbouring fills
    for (const z of this.cfg.zones) {
      const enabled = (p.localEnabled.get(z.id) ?? true) && z.enabled;
      if (!enabled) continue;
      const sev = this.effectiveSeverity(z, p);
      const st = p.states.get(z.id);
      if ((sev === "CAUTION" || sev === "DANGER") && st && st.nearest_range_m != null) {
        this.drawObject(z, sev, st, p.animMs, S);
      }
    }
  }

  // --- drawing primitives ---

  private trace(points: number[][], S: number): void {
    const ctx = this.ctx;
    ctx.beginPath();
    points.forEach(([x, y], i) =>
      i ? ctx.lineTo(x * S, y * S) : ctx.moveTo(x * S, y * S));
    ctx.closePath();
  }

  private drawZone(z: ZoneCfg, sev: Severity, p: RenderParams, S: number): void {
    const ctx = this.ctx;
    const style = SEVERITY[sev];

    this.trace(z.polygon_norm, S);
    ctx.fillStyle = style.fill;
    ctx.fill();
    if (style.hatch) this.hatch(z.polygon_norm, S);

    // DANGER pulses (motion channel): border alpha + width breathe
    let lw = style.lineWidth;
    let alpha = 1;
    if (style.pulse) {
      const t = 0.5 + 0.5 * Math.sin(p.animMs / 170);
      lw = style.lineWidth + t * 2;
      alpha = 0.55 + 0.45 * t;
    }
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.setLineDash(style.dash);
    ctx.lineWidth = lw;
    ctx.strokeStyle = style.stroke;
    this.trace(z.polygon_norm, S);
    ctx.stroke();
    ctx.restore();
    ctx.setLineDash([]);

    // small zone label
    const [cx, cy] = z.centroid;
    this.text(zoneName(z.id), cx * S, cy * S - S * 0.045, S * 0.020, THEME.textDim);
  }

  private drawDisabledZone(z: ZoneCfg, S: number): void {
    const ctx = this.ctx;
    ctx.save();
    ctx.globalAlpha = 0.5;
    ctx.setLineDash([3, 4]);
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(120,128,140,0.35)";
    this.trace(z.polygon_norm, S);
    ctx.stroke();
    ctx.restore();
    ctx.setLineDash([]);
  }

  /** Diagonal hatch clipped to the polygon — the UNKNOWN texture (color-blind redundant). */
  private hatch(points: number[][], S: number): void {
    const ctx = this.ctx;
    ctx.save();
    this.trace(points, S);
    ctx.clip();
    ctx.strokeStyle = THEME.hatch;
    ctx.lineWidth = 1;
    const step = S * 0.022;
    ctx.beginPath();
    for (let d = -S; d < S; d += step) {
      ctx.moveTo(d, 0);
      ctx.lineTo(d + S, S);
    }
    ctx.stroke();
    ctx.restore();
  }

  /** Generic blob (phase-1): class-specific icons are phase-2/camera (FR-06 note). */
  private drawObject(z: ZoneCfg, sev: Severity, st: ZoneState, animMs: number, S: number): void {
    const ctx = this.ctx;
    const style = SEVERITY[sev];
    const [cx, cy] = z.centroid;
    const x = cx * S;
    const y = cy * S;
    const r = S * 0.032;

    // pulsing ring on DANGER (motion channel)
    let ringW = 3;
    if (style.pulse) ringW = 3 + (0.5 + 0.5 * Math.sin(animMs / 170)) * 3;

    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = THEME.blobFill;
    ctx.fill();
    ctx.lineWidth = ringW;
    ctx.strokeStyle = style.stroke;
    ctx.stroke();

    // redundant glyph (no-color channel)
    this.text(style.glyph, x, y + r * 0.05, r * 1.05, style.stroke);

    // range readout (06 §6.2): nearest distance beside the icon
    const rng = st.nearest_range_m;
    if (rng != null) {
      this.text(`${rng.toFixed(1)} m`, x, y + r + S * 0.028, S * 0.024, THEME.text);
    }
  }

  private drawTruck(S: number): void {
    const ctx = this.ctx;
    this.trace(this.cfg.truckOutline, S);
    ctx.fillStyle = THEME.truckFill;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = THEME.truckStroke;
    ctx.stroke();
    const [tx, ty] = this.cfg.truckCentroid;
    this.text("CAB", tx * S, ty * S, S * 0.022, THEME.textDim);
  }

  private drawOrientation(S: number): void {
    // truck nose at top (config convention) → FRONT marker up, REAR down
    this.text("▲", this.cfg.truckCentroid[0] * S, S * 0.03, S * 0.026, "rgba(150,164,184,0.5)");
  }

  private text(s: string, x: number, y: number, px: number, color: string): void {
    const ctx = this.ctx;
    ctx.fillStyle = color;
    ctx.font = `${Math.round(px)}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(s, x, y);
  }
}
