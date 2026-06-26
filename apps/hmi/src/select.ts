// Priority selection — which zone owns the banner/ear, and what the audio engine should sound.
//
// PURE and browser-free so it unit-tests under Node. Encodes two policies from the spec:
//   * Primary alert (05 §5.6): the banner + ear follow the highest risk_weight × severity.
//   * Audio (05 §5.5): sound the SINGLE worst active severity; park-standby or mute => silent.

import type { Severity, ZoneState } from "./types";

/** Active-alert rank: only CAUTION/DANGER are "active". SAFE/UNKNOWN are not banner/audio drivers. */
export function activeRank(sev: Severity): number {
  return sev === "DANGER" ? 2 : sev === "CAUTION" ? 1 : 0;
}

export interface ZonePriority {
  id: string;
  risk_weight: number;
}

/**
 * Worst active zone by `risk_weight × severityRank` (05 §5.6). Returns null when nothing is
 * actively alerting (all SAFE/UNKNOWN). Ties resolve to the higher raw severity, then first seen.
 */
export function worstActiveZone(
  zones: ZonePriority[],
  states: Map<string, ZoneState>,
): { id: string; state: ZoneState } | null {
  let best: { id: string; state: ZoneState } | null = null;
  let bestScore = 0;
  let bestRank = 0;
  for (const z of zones) {
    const st = states.get(z.id);
    if (!st) continue;
    const rank = activeRank(st.severity);
    if (rank === 0) continue;
    const score = z.risk_weight * rank;
    if (score > bestScore || (score === bestScore && rank > bestRank)) {
      bestScore = score;
      bestRank = rank;
      best = { id: z.id, state: st };
    }
  }
  return best;
}

/**
 * Drop zones the operator switched off (settings toggle) or the config disabled, so the ear and
 * banner agree with the map (scene.ts greys these out). A disabled zone keeps its last *retained*
 * wire state in the store — without this filter it would keep beeping and owning the banner for a
 * zone the driver is shown as off (alarm fatigue + inconsistency, 05 §5.5/§5.6).
 */
export function activeZoneStates(
  states: Map<string, ZoneState>,
  localEnabled: Map<string, boolean>,
  configEnabled: Map<string, boolean>,
): Map<string, ZoneState> {
  const m = new Map<string, ZoneState>();
  for (const [id, st] of states) {
    if ((localEnabled.get(id) ?? true) && (configEnabled.get(id) ?? true)) m.set(id, st);
  }
  return m;
}

export type AudioTarget = "SILENT" | "CAUTION" | "DANGER";

/**
 * The single worst severity to sound (05 §5.5). Park-standby and timed mute both force SILENT
 * (audio suppressed) while visuals are untouched elsewhere. Only CAUTION/DANGER make sound;
 * UNKNOWN is visual + a separate one-shot fault chime (handled by the audio engine).
 */
export function audioTarget(
  states: Iterable<ZoneState>,
  opts: { standby: boolean; muted: boolean },
): AudioTarget {
  if (opts.standby || opts.muted) return "SILENT";
  let worst = 0;
  for (const st of states) {
    worst = Math.max(worst, activeRank(st.severity));
    if (worst === 2) break;
  }
  return worst === 2 ? "DANGER" : worst === 1 ? "CAUTION" : "SILENT";
}

/** Any zone reporting park-standby ⇒ standby (fusion sets the same value on every zone/tick). */
export function isStandby(states: Iterable<ZoneState>): boolean {
  for (const st of states) if (st.standby) return true;
  return false;
}
