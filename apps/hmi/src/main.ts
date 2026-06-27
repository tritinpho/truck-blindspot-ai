// HMI entry point (S3). Wires the broker → store → render loop and ties together the scene,
// audio, liveness, and views. The full in-cabin HMI of 06-hmi-design.md, driven only by MQTT.
//
//   data in:  bsw/zone/#  (severity per zone)   + bsw/health/fusion (liveness)
//   audio:    single worst severity (05 §5.5)    + rate-limited fault chime
//   liveness: local-receipt freshness clock (ADR-0006/0008) → WARMING_UP / MONITORING / SIGNAL_LOST
//   views:    drive (Canvas) · settings (→ bsw/cmd) · hidden diagnostics

import { loadSceneConfig } from "./config";
import { createState, isMuted, lastFusionReceipt, zoneStates } from "./store";
import { evaluateLiveness } from "./liveness";
import { activeZoneStates, audioTarget, isStandby, worstActiveZone, type AudioTarget } from "./select";
import { Scene } from "./scene";
import { AudioEngine } from "./audio";
import { Bus } from "./bus";
import { UI, type BannerVM, type UICallbacks } from "./ui";
import { setLang } from "./i18n";
import { applyTheme, initTheme } from "./theme";
import type { Severity } from "./types";

const BROKER = import.meta.env.VITE_BROKER_WS ?? "ws://localhost:9001";
const MUTE_MS = 60_000; // timed mute (never hides visuals)

const cfg = loadSceneConfig();
initTheme(); // apply persisted/auto day-night theme before the first render (ADR-0009 vanilla TS)
const state = createState(cfg.zones.map((z) => z.id));
const zonePriorities = cfg.zones.map((z) => ({ id: z.id, risk_weight: z.risk_weight }));
const configEnabled = new Map(cfg.zones.map((z) => [z.id, z.enabled]));

const scene = new Scene(document.getElementById("scene") as HTMLCanvasElement, cfg);
const audio = new AudioEngine();
const bus = new Bus(BROKER, state, new Set(cfg.zones.map((z) => z.id)));

const callbacks: UICallbacks = {
  toggleMute() {
    state.audio.mutedUntilMono = state.audio.mutedUntilMono ? null : performance.now() + MUTE_MS;
  },
  setVolume(v) { state.audio.volume = v; audio.setVolume(v); },
  setLang(l) { setLang(l); state.lang = l; ui.relocalize(); },
  setTheme(m) { applyTheme(m); },
  setView(v) {
    state.view = v;
    ui.showView(v);
    bus.setDiagnostics(v === "diagnostics");
    audio.ensure(); // a view switch is a user gesture — unlock audio
    if (v === "drive") scene.fit();
  },
  setThreshold(zoneId, caution_m, danger_m) {
    bus.publishCmd("set_threshold", { zone_id: zoneId, caution_m, danger_m });
  },
  setZoneEnabled(zoneId, enabled) {
    state.localEnabled.set(zoneId, enabled);
    bus.publishCmd(enabled ? "enable_zone" : "disable_zone", { zone_id: zoneId });
  },
  userGesture() { audio.ensure(); },
};

const ui = new UI(cfg, state, callbacks);
scene.fit();
window.addEventListener("resize", () => scene.fit());

// Build the audio graph at startup (best-effort). Autoplay policy starts the context SUSPENDED
// until a gesture resumes it (the once pointer/keydown listener in ui.ts), or it starts RUNNING
// immediately if Chromium is launched with --autoplay-policy=no-user-gesture-required (the kiosk
// flag). Either way the graph now exists, so `audio.needsGesture` reflects the true state and the
// "tap for sound" hint shows in a never-touched cabin instead of silently having no audio at all.
audio.ensure();

// --- transition tracking for the fault chime ---
const prevSeverity = new Map<string, Severity>();
let prevPhase = state.phase;

function renderFrame(): void {
  const now = performance.now();

  const liveness = evaluateLiveness({
    nowMono: now,
    lastFusionReceiptMono: lastFusionReceipt(state),
    sawFirstZone: state.sawFirstZone,
    fusionFaultLatched: state.fusionFaultLatched,
  });
  state.phase = liveness.phase;

  const states = zoneStates(state);
  // Disabled zones (operator toggle or config) are greyed on the map; drop them here so they
  // don't keep driving the ear/banner from their stale retained state (05 §5.5/§5.6).
  const activeStates = activeZoneStates(states, state.localEnabled, configEnabled);
  // Standby is read from ACTIVE zones only: a disabled or stale-retained zone must not drive audio
  // policy. Otherwise a zone left with a retained standby=true (e.g. park → operator disables it →
  // vehicle leaves park, so fusion stops refreshing it) would keep audio globally suppressed while
  // the enabled zones are actively in DANGER.
  const standby = isStandby(activeStates.values());
  const muted = isMuted(state, now);

  // --- audio: single worst severity while monitoring; standby/mute → silent ---
  const target: AudioTarget =
    liveness.phase === "MONITORING" ? audioTarget(activeStates.values(), { standby, muted }) : "SILENT";
  audio.update(target, now);

  // --- fault chime: a zone going UNKNOWN under a healthy system, or the system going SIGNAL_LOST ---
  if (!muted && !standby) {
    if (prevPhase === "MONITORING" && liveness.phase === "SIGNAL_LOST") {
      audio.chime(now); // whole-system fault (rate-limited internally)
    } else if (liveness.phase === "MONITORING") {
      for (const [id, st] of activeStates) {
        const prev = prevSeverity.get(id);
        if (prev && prev !== "UNKNOWN" && st.severity === "UNKNOWN") { audio.chime(now); break; }
      }
    }
  }
  for (const [id, st] of states) prevSeverity.set(id, st.severity);
  prevPhase = liveness.phase;

  // --- primary-alert banner: worst risk_weight × severity (05 §5.6) ---
  let banner: BannerVM | null = null;
  if (liveness.phase === "MONITORING") {
    const worst = worstActiveZone(zonePriorities, activeStates);
    if (worst) {
      banner = {
        severity: worst.state.severity,
        zoneId: worst.id,
        rangeM: worst.state.nearest_range_m ?? null,
        objectClass: worst.state.object_class ?? null,
      };
    }
  }

  ui.render({
    phase: liveness.phase,
    live: liveness.live,
    animMs: now,
    banner,
    health: state.fusionHealth,
    muted,
    muteRemainingS: state.audio.mutedUntilMono ? (state.audio.mutedUntilMono - now) / 1000 : 0,
    audioNeedsGesture: audio.needsGesture,
  });

  if (state.view === "drive") {
    scene.render({ states, phase: liveness.phase, localEnabled: state.localEnabled, animMs: now });
  }
}

// A single render error must never permanently kill the loop: requestAnimationFrame is re-armed in
// `finally`, so a bad frame (e.g. an unexpected wire value the boundary missed) is logged and the
// next frame still runs — the liveness clock then degrades the map to UNKNOWN if data really
// stopped (ADR-0006), rather than leaving a frozen last frame on screen.
function loop(): void {
  try {
    renderFrame();
  } catch (e) {
    console.error("[hmi] render loop error (continuing):", e);
  } finally {
    requestAnimationFrame(loop);
  }
}

requestAnimationFrame(loop);

// Dev-only debug handle (guarded by import.meta.env.DEV → stripped from `vite build` output).
// Lets the console seed zone state for visual checks when no broker is running.
if (import.meta.env.DEV) {
  (globalThis as unknown as { __bsw?: unknown }).__bsw = { state, cfg, bus, audio };
}
