// Wire-input validation for the anonymous-broker trust boundary (06 §6.5). PURE and browser-free
// so it unit-tests under `node --test`, exactly like liveness.ts / select.ts.
//
// The HMI renders whatever fusion — or any peer on the anonymous broker (version skew or a spoof)
// — publishes on bsw/zone/#, so a zone message must be checked BEFORE the rAF loop keys on it.
// Two fields are load-bearing: an unknown `severity` indexes SEVERITY[...] (undefined), and a
// non-numeric `nearest_range_m` reaches `.toFixed()` in the banner/scene — either throws inside
// the loop, which only re-arms requestAnimationFrame at its end, so one bad message freezes the
// whole display (the frozen-green failure mode ADR-0006 exists to avoid).

import type { ZoneState } from "./types";

const VALID_SEVERITIES = new Set(["SAFE", "CAUTION", "DANGER", "UNKNOWN"]);

/** A range the renderer can safely call `.toFixed()` on: a finite number, or null/absent. Fusion
 * legitimately publishes a null range while holding a last-known severity through a stale window
 * (engine.py `_update_zone`), so null must be accepted — only wrong *types* are rejected. */
export function isRenderableRange(v: unknown): boolean {
  return v == null || (typeof v === "number" && Number.isFinite(v));
}

/** Is this a zone message the renderer can safely consume? Guards every field the rAF loop trusts
 * (zone_id key, severity lookup, nearest_range_m formatting). A failing message is dropped at the
 * bus so the zone keeps its last good state and ages to UNKNOWN via the liveness clock (fail-loud). */
export function isRenderableZone(z: unknown): z is ZoneState {
  const o = z as Record<string, unknown> | null;
  return !!o
    && typeof o.zone_id === "string" && o.zone_id.length > 0
    && typeof o.severity === "string" && VALID_SEVERITIES.has(o.severity)
    && isRenderableRange(o.nearest_range_m);
}
