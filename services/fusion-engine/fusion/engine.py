"""Fusion engine core logic.

Two layers, both MQTT-free so they unit-test directly (L2):
  * `zone_severity` — pure instantaneous severity from a zone's readings (S1).
  * `FusionEngine`  — stateful: debounce/hysteresis, confirm-by-range, context modifiers,
    and local-arrival staleness, per 05-warning-logic.md (§5.2-§5.4) and ADR-0007/0008.

Clock discipline (ADR-0008): staleness is measured from **local arrival time** (a monotonic
ms clock supplied by the caller), never from a message `ts`. The wire `ts` is passed through
to the published payload only.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

SAFE = "SAFE"
CAUTION = "CAUTION"
DANGER = "DANGER"
UNKNOWN = "UNKNOWN"

_RANK = {SAFE: 0, CAUTION: 1, DANGER: 2}
VRU_CLASSES = {"pedestrian", "cyclist", "motorbike"}


def _step_down(sev: str) -> str:
    return CAUTION if sev == DANGER else SAFE


def _valid_range(rng) -> bool:
    """A usable range: a finite, non-negative real number. Rejects the wire shapes that would
    otherwise reach `float()` in the tick — strings, lists, bools, NaN/Inf (json.loads accepts
    `NaN`/`Infinity` by default), negatives."""
    return (isinstance(rng, (int, float)) and not isinstance(rng, bool)
            and math.isfinite(rng) and rng >= 0)


def _zone_side(zone_id: str) -> str | None:
    if "RIGHT" in zone_id:
        return "right"
    if "LEFT" in zone_id:
        return "left"
    return None


# --------------------------------------------------------------------------- config

@dataclass
class ZoneCfg:
    zone_id: str
    enabled: bool
    caution_m: float
    danger_m: float
    risk_weight: float = 1.0


@dataclass
class Config:
    zones: dict[str, ZoneCfg]
    sensor_to_zone: dict[str, str]
    zone_to_sensors: dict[str, list[str]]
    tun: dict = field(default_factory=dict)      # confirm/release/margin/immediate/stale*/vru
    context: dict = field(default_factory=dict)  # boost factors, reverse zones, speed bands

    @property
    def zone_ids(self) -> list[str]:
        return [zid for zid, z in self.zones.items() if z.enabled]


def load_config(zones_path: Path, sensors_path: Path) -> Config:
    """Load zones + sensors config, build the reverse zone -> sensors index (FR-02/03),
    and gather the warning-logic tunables (05 §5.8)."""
    zc = json.loads(Path(zones_path).read_text(encoding="utf-8"))
    sc = json.loads(Path(sensors_path).read_text(encoding="utf-8"))
    d = zc.get("defaults", {})

    zones: dict[str, ZoneCfg] = {}
    for z in zc["zones"]:
        zones[z["id"]] = ZoneCfg(
            zone_id=z["id"],
            enabled=z.get("enabled", True),
            caution_m=float(z.get("caution_m", d.get("caution_m", 1.5))),
            danger_m=float(z.get("danger_m", d.get("danger_m", 0.8))),
            risk_weight=float(z.get("risk_weight", 1.0)),
        )

    sensor_to_zone: dict[str, str] = {}
    zone_to_sensors: dict[str, list[str]] = {zid: [] for zid in zones}
    for s in sc["sensors"]:
        if s.get("enabled", True) is False:
            continue  # phase-2 camera etc.
        sensor_to_zone[s["id"]] = s["zone"]
        zone_to_sensors.setdefault(s["zone"], []).append(s["id"])

    ctx_in = zc.get("context", {})
    boost = ctx_in.get("turn_signal_boost", {})
    bands = ctx_in.get("speed_bands_kph", {})
    context = {
        "factor_caution_m": float(boost.get("factor_caution_m", 1.0)),
        "factor_danger_m": float(boost.get("factor_danger_m", 1.0)),
        "reverse_boost_zones": set(ctx_in.get("reverse_boost_zones", [])),
        "park_standby_mute_audio": bool(ctx_in.get("park_standby_mute_audio", False)),
        "speed_low_max": float(bands.get("low_max", 30)),
        "speed_high_min": float(bands.get("high_min", 50)),
    }
    tun = {
        "confirm": int(d.get("confirm", 2)),
        "release": int(d.get("release", 4)),
        "release_margin_m": float(d.get("release_margin_m", 0.2)),
        "immediate_danger_factor": float(d.get("immediate_danger_factor", 0.6)),
        "stale_after_ms": int(sc.get("stale_after_ms", 700)),
        "stale_confirm": int(zc.get("alerting", {}).get("stale_confirm", 2)),
        "vru_multiplier": float(zc.get("vru_threshold_multiplier", 1.0)),
    }
    return Config(zones, sensor_to_zone, zone_to_sensors, tun=tun, context=context)


# ------------------------------------------------------------------ instantaneous (S1)

def zone_severity(zone: ZoneCfg, readings: list[dict]) -> tuple[str, float | None]:
    """Instantaneous severity for one zone (no debounce/context). Used by S1 tests and as
    the building block inside FusionEngine."""
    healthy = [r for r in readings if r.get("health", "ok") == "ok"]
    if not healthy:
        return UNKNOWN, None
    present = [r for r in healthy if r.get("present") and r.get("range_m") is not None]
    if not present:
        return SAFE, None  # healthy but clear -- empty-present => SAFE (R2-6)
    nearest = min(float(r["range_m"]) for r in present)
    if nearest <= zone.danger_m:
        return DANGER, nearest
    if nearest <= zone.caution_m:
        return CAUTION, nearest
    return SAFE, nearest


# ----------------------------------------------------------------------- stateful core

@dataclass
class ZoneRuntime:
    severity: str = UNKNOWN  # no data yet -> fail loud, not a fake SAFE (NFR-04/NFR-12)
    confirm: int = 0
    release: int = 0
    stale_miss: int = 0


class FusionEngine:
    """Stateful per-zone warning logic. Feed readings via `ingest`, then call `tick` on a
    fixed cadence to get the per-zone wire payloads to publish."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.readings: dict[str, tuple[dict, float]] = {}  # sid -> (reading, arrival_mono_ms)
        self.rt: dict[str, ZoneRuntime] = {z: ZoneRuntime() for z in cfg.zones}

    def ingest(self, reading: dict, arrival_mono_ms: float) -> None:
        sid = reading.get("sensor_id")
        if sid not in self.cfg.sensor_to_zone:
            return
        # Sanitize at the trust boundary (anonymous broker): a malformed range_m must never reach
        # float() in the tick (it would crash the whole engine), and a present-without-range reading
        # must not be silently swallowed into SAFE. Both are dropped here, so the zone ages toward
        # UNKNOWN (fail-loud, NFR-04) instead of crashing or faking "all clear". 04 §4.3.1 requires
        # present=true to carry range_m; validate_message.contract_lint flags the same violations.
        rng = reading.get("range_m")
        if rng is not None and not _valid_range(rng):
            return
        if reading.get("present") and rng is None:
            return
        self.readings[sid] = (reading, arrival_mono_ms)

    # --- runtime reconfiguration (bsw/cmd, 04 §4.3.6 / 05 §5.8) ---

    def apply_cmd(self, op: str, args: dict | None) -> tuple[bool, str]:
        """Apply a live bsw.cmd to the in-memory config (set_threshold / enable_zone /
        disable_zone). Returns (changed, human-readable detail) for logging. Pure: mutates only
        this engine's Config so it unit-tests without a broker. `reload_config` reloads from disk
        and is handled one layer up (FusionService, which owns the file paths); set_volume/mute are
        HMI-local and ignored here. Tunables are §5.8; this is the path the S6 threshold sweep uses."""
        args = args or {}
        if op == "set_threshold":
            zid = args.get("zone_id")
            z = self.cfg.zones.get(zid)
            if z is None:
                return False, f"unknown zone {zid!r}"
            changed: list[str] = []
            for key in ("danger_m", "caution_m", "risk_weight"):
                if args.get(key) is None:
                    continue
                try:
                    val = float(args[key])
                except (TypeError, ValueError):
                    return False, f"{zid} {key}: not a number ({args[key]!r})"
                if val <= 0:
                    return False, f"{zid} {key}: must be > 0 ({val})"
                setattr(z, key, val)
                changed.append(f"{key}={val:g}")
            return (bool(changed), f"{zid} " + (" ".join(changed) if changed else "no-op"))
        if op in ("enable_zone", "disable_zone"):
            zid = args.get("zone_id")
            z = self.cfg.zones.get(zid)
            if z is None:
                return False, f"unknown zone {zid!r}"
            z.enabled = op == "enable_zone"
            return True, f"{zid} enabled={z.enabled}"
        if op in ("set_volume", "mute"):
            return False, f"{op}: HMI-local, fusion ignores"
        return False, f"unknown op {op!r}"

    def replace_config(self, cfg: Config) -> None:
        """Swap in a freshly-loaded Config (reload_config) and reconcile per-zone runtime: keep
        state for surviving zones (no flicker on reload), init new zones to UNKNOWN (fail-loud,
        not a fake SAFE), drop removed ones. Existing readings stay keyed by sensor_id."""
        self.cfg = cfg
        self.rt = {zid: self.rt.get(zid, ZoneRuntime()) for zid in cfg.zones}

    def tick(self, now_mono_ms: float, now_epoch_ms: int, vehicle: dict | None = None) -> list[dict]:
        standby = self._is_standby(vehicle)
        return [self._update_zone(zid, now_mono_ms, now_epoch_ms, vehicle, standby)
                for zid in self.cfg.zone_ids]

    # --- internals ---

    def _fresh_healthy(self, zid: str, now_mono_ms: float) -> list[dict]:
        out = []
        for sid in self.cfg.zone_to_sensors.get(zid, []):
            entry = self.readings.get(sid)
            if entry is None:
                continue
            reading, arr = entry
            if now_mono_ms - arr > self.cfg.tun["stale_after_ms"]:
                continue  # stale -- local-arrival age, ADR-0008
            if reading.get("health", "ok") != "ok":
                continue
            out.append(reading)
        return out

    def _effective_thresholds(self, zone: ZoneCfg, vehicle, object_class) -> tuple[float, float]:
        caution, danger = zone.caution_m, zone.danger_m
        # VRU widening (phase-2; object_class is None for phase-1 ultrasonic). factor>1 = sooner.
        if object_class in VRU_CLASSES:
            m = self.cfg.tun["vru_multiplier"]
            caution, danger = caution * m, danger * m
        if vehicle:
            ctx = self.cfg.context
            side = _zone_side(zone.zone_id)
            ts = vehicle.get("turn_signal", "none")
            boosted = (side is not None and (ts == side or ts == "hazard"))
            if vehicle.get("gear") == "reverse" and zone.zone_id in ctx["reverse_boost_zones"]:
                boosted = True
            if boosted:  # R2-1: factor>1 WIDENS the trigger distance -> warns sooner
                caution *= ctx["factor_caution_m"]
                danger *= ctx["factor_danger_m"]
        return caution, danger

    def _is_standby(self, vehicle) -> bool:
        if not vehicle or not self.cfg.context.get("park_standby_mute_audio"):
            return False
        return vehicle.get("gear") == "park" and (vehicle.get("speed_kph") or 0) <= 1.0

    def _update_zone(self, zid, now_mono_ms, now_epoch_ms, vehicle, standby) -> dict:
        zone = self.cfg.zones[zid]
        rt = self.rt[zid]
        healthy = self._fresh_healthy(zid, now_mono_ms)

        # --- staleness / fault -> UNKNOWN, debounced by stale_confirm (anti-flicker, 05 §5.3) ---
        if not healthy:
            rt.stale_miss += 1
            if rt.stale_miss >= self.cfg.tun["stale_confirm"]:
                rt.severity, rt.confirm, rt.release = UNKNOWN, 0, 0
            # hold last-known severity until stale_confirm trips; _payload sets stale iff UNKNOWN
            return self._payload(zid, rt.severity, None, None, now_epoch_ms,
                                 reason="no healthy reading", standby=standby)
        rt.stale_miss = 0

        present = [r for r in healthy if r.get("present") and r.get("range_m") is not None]
        object_class = next((r.get("object_class") for r in healthy if r.get("object_class")), None)
        eff_caution, eff_danger = self._effective_thresholds(zone, vehicle, object_class)

        if not present:
            nearest, target = None, SAFE
        else:
            nearest = min(float(r["range_m"]) for r in present)
            target = DANGER if nearest <= eff_danger else CAUTION if nearest <= eff_caution else SAFE

        # recover from UNKNOWN immediately on a fresh healthy reading (05 §5.3 state machine)
        if rt.severity == UNKNOWN:
            rt.severity, rt.confirm, rt.release = target, 0, 0
            return self._payload(zid, target, nearest, object_class, now_epoch_ms,
                                 reason="recovered", standby=standby)

        cur = rt.severity
        cr, tr = _RANK[cur], _RANK[target]
        if tr > cr:  # escalate -- fast (confirm-by-range, ADR-0007)
            rt.release = 0
            deep = (target == DANGER and nearest is not None
                    and nearest <= self.cfg.tun["immediate_danger_factor"] * eff_danger)
            required = 1 if deep else self.cfg.tun["confirm"]
            rt.confirm += 1
            if rt.confirm >= required:
                rt.severity, rt.confirm = target, 0
        elif tr < cr:  # de-escalate -- slow: one rank, needs margin + release ticks (hysteresis)
            rt.confirm = 0
            leave = eff_danger if cur == DANGER else eff_caution
            cleared = nearest is None or nearest > leave + self.cfg.tun["release_margin_m"]
            if cleared:
                rt.release += 1
                if rt.release >= self.cfg.tun["release"]:
                    rt.severity, rt.release = _step_down(cur), 0
            else:
                rt.release = 0
        else:
            rt.confirm = rt.release = 0

        reason = f"nearest={nearest:.2f};d<={eff_danger:.2f},c<={eff_caution:.2f}" if nearest is not None \
            else f"clear;d<={eff_danger:.2f},c<={eff_caution:.2f}"
        return self._payload(zid, rt.severity, nearest, object_class, now_epoch_ms,
                             reason=reason, standby=standby)

    def _payload(self, zid, severity, nearest, object_class, ts, *, reason, standby, stale=False) -> dict:
        return {
            "schema": "bsw.zone_state/1",
            "zone_id": zid,
            "ts": ts,
            "severity": severity,
            "object_class": object_class,
            "nearest_range_m": nearest,
            "source": "fusion",
            "reason": reason,
            "stale": stale or severity == UNKNOWN,
            "standby": standby,
        }
