// Liveness clock — the HMI's fail-loud core (ADR-0006 #3, ADR-0008 #2, FR-15, NFR-12).
//
// PURE and browser-free so it unit-tests directly under Node (no DOM, no bundler).
//
// The single normative rule (ADR-0008): freshness is measured from the LOCAL RECEIPT TIME of
// fusion messages on the consumer's OWN monotonic clock — NEVER from a message `ts` (a foreign,
// possibly pre-NTP / boot-relative clock). The caller passes `performance.now()` as `nowMono`
// and the local receipt time of the freshest fusion signal it has seen.

import type { SystemPhase } from "./types";

export const DEFAULT_FRESHNESS_MS = 1000;

export interface LivenessInputs {
  /** consumer's local monotonic clock now (performance.now()). */
  nowMono: number;
  /** local receipt time of the freshest fusion signal: max(last zone, last heartbeat); null if none. */
  lastFusionReceiptMono: number | null;
  /** have we ever received a zone snapshot? gates WARMING_UP (NFR-12). */
  sawFirstZone: boolean;
  /** a bsw/health/fusion status:"fault" (incl. the broker LWT) trips SIGNAL_LOST at once. */
  fusionFaultLatched: boolean;
  /** freshness window; default 1 s. */
  freshnessMs?: number;
}

export interface LivenessResult {
  phase: SystemPhase;
  /** age of the freshest fusion signal in ms (for display); null if none yet. */
  ageMs: number | null;
  /** true only while monitoring on fresh data — drives the animating "alive" pip. */
  live: boolean;
}

/**
 * Decide the system phase from local-clock freshness.
 *
 *   - no zone snapshot yet            → WARMING_UP  (boot; never silently "all clear")
 *   - fresh fusion signal, no fault   → MONITORING  (live)
 *   - stale (> window) or fault       → SIGNAL_LOST (whole map degrades to UNKNOWN)
 *
 * SIGNAL_LOST ⇄ MONITORING recovers automatically when fresh data resumes.
 */
export function evaluateLiveness(i: LivenessInputs): LivenessResult {
  const freshnessMs = i.freshnessMs ?? DEFAULT_FRESHNESS_MS;
  const ageMs = i.lastFusionReceiptMono == null ? null : i.nowMono - i.lastFusionReceiptMono;

  if (!i.sawFirstZone) {
    return { phase: "WARMING_UP", ageMs, live: false };
  }
  const fresh = !i.fusionFaultLatched && ageMs != null && ageMs <= freshnessMs;
  if (fresh) {
    return { phase: "MONITORING", ageMs, live: true };
  }
  return { phase: "SIGNAL_LOST", ageMs, live: false };
}
