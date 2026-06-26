"""Pure metric cores shared by the eval tools (no MQTT, no I/O) so they unit-test in CI.

  * summarize_events  — recompute report metrics from a transition log (11 §11.6 replay).
  * LatencyPairer     — single-observer, single-clock end-to-end latency (ADR-0008 #3).
  * danger_latency_ms — indicative danger-path latency from a deterministic timeline (S6 sweep).
  * danger_dwell_frac — fraction of a run a zone spent in DANGER (false-alarm exposure, S6).
"""
from __future__ import annotations

from dataclasses import dataclass, field

FLICKER_MS = 1000  # a severity reversal (A→B→A) within this window counts as flicker (FR-09)


def danger_latency_ms(ts: list[int], rng: list[float | None], sev: list[str],
                      danger_m: float) -> int | None:
    """Indicative danger-path latency (ms): time from an object *crossing into* base danger_m
    (a prior tick was outside it) to the zone confirming DANGER. None when there is no such
    crossing (e.g. static-from-start, where the first reading recovers straight to DANGER), DANGER
    never fires, or DANGER preceded the crossing (a context boost warned early — not a latency).
    This isolates the operational approach case the NFR-01 danger-path budget is about."""
    crossing = None
    for i in range(1, len(ts)):
        outside_before = rng[i - 1] is None or rng[i - 1] > danger_m
        if outside_before and rng[i] is not None and rng[i] <= danger_m:
            crossing = ts[i]
            break
    danger = next((ts[i] for i in range(len(ts)) if sev[i] == "DANGER"), None)
    if crossing is None or danger is None or danger < crossing:
        return None
    return danger - crossing


def danger_dwell_frac(sev: list[str]) -> float:
    """Fraction of ticks a zone spent in DANGER — the sim's false-alarm exposure proxy for a
    nuisance scenario (an object that should hold CAUTION but is noisily pushed into DANGER)."""
    return sev.count("DANGER") / len(sev) if sev else 0.0


def summarize_events(events: list[dict]) -> dict:
    """Recompute metrics from `bsw` zone-transition events (the eventlog JSONL rows).

    Each event: {ts, zone_id, from, to, nearest_range_m, reason}. Deterministic, so a recorded
    run replays to identical numbers for the report (11 §11.6)."""
    per_zone: dict[str, dict] = {}
    seq: dict[str, list[dict]] = {}
    for e in events:
        z = e["zone_id"]
        d = per_zone.setdefault(z, {"transitions": 0, "to_danger": 0, "to_unknown": 0, "flicker": 0})
        d["transitions"] += 1
        if e.get("to") == "DANGER":
            d["to_danger"] += 1
        if e.get("to") == "UNKNOWN":
            d["to_unknown"] += 1
        seq.setdefault(z, []).append(e)

    for z, evs in seq.items():
        flicker = 0
        for a, b in zip(evs, evs[1:]):
            # a quick reversal back to where we came from (e.g. CAUTION→DANGER→CAUTION) = flicker
            if a.get("from") == b.get("to") and (b["ts"] - a["ts"]) <= FLICKER_MS:
                flicker += 1
        per_zone[z]["flicker"] = flicker

    total = {
        "events": len(events),
        "zones": len(per_zone),
        "to_danger": sum(d["to_danger"] for d in per_zone.values()),
        "to_unknown": sum(d["to_unknown"] for d in per_zone.values()),
        "flicker": sum(d["flicker"] for d in per_zone.values()),
    }
    return {"per_zone": per_zone, "total": total}


@dataclass
class _ZoneLat:
    armed: float | None = None
    in_danger: bool = False


@dataclass
class LatencyPairer:
    """Pair a *stimulus* (an object entered danger range, seen on a sensor reading) with the next
    *effect* (that zone went DANGER), both stamped on the OBSERVER's own clock → a single-clock
    delta valid across unsynced nodes (ADR-0008 #3). Per zone: arm on the first stimulus, fire on
    the next DANGER, disarm when the zone leaves DANGER so the next approach is measured fresh."""
    latencies: list[tuple[str, float]] = field(default_factory=list)
    _z: dict[str, _ZoneLat] = field(default_factory=dict)

    def stimulus(self, zone: str, t: float) -> None:
        st = self._z.setdefault(zone, _ZoneLat())
        if not st.in_danger and st.armed is None:
            st.armed = t

    def effect(self, zone: str, severity: str, t: float) -> None:
        st = self._z.setdefault(zone, _ZoneLat())
        if severity == "DANGER":
            if st.armed is not None and not st.in_danger:
                self.latencies.append((zone, t - st.armed))
            st.in_danger, st.armed = True, None
        elif severity in ("SAFE", "UNKNOWN"):
            # object gone / sensor lost → clear so the next approach is measured fresh.
            st.in_danger, st.armed = False, None
        # CAUTION is transient on the way to/from DANGER — keep the timer armed (don't disarm).

    def values_ms(self) -> list[float]:
        return [ms for _, ms in self.latencies]

    def summary(self) -> dict:
        v = sorted(self.values_ms())
        if not v:
            return {"n": 0}
        return {"n": len(v), "min": v[0], "max": v[-1],
                "mean": round(sum(v) / len(v), 1), "p50": v[len(v) // 2]}
