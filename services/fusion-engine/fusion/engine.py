"""Fusion engine core logic (S1 MVP).

Pure functions over the message contracts: load config, map sensor -> zone, compute
per-zone severity. Deliberately free of MQTT so it can be unit-tested directly (L2, S2).

S1 scope: severity only. Debounce/hysteresis, confirm-by-range, context modifiers, and
local-arrival staleness land in S2 (05 §5.3-§5.4, ADR-0007/0008).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SAFE = "SAFE"
CAUTION = "CAUTION"
DANGER = "DANGER"
UNKNOWN = "UNKNOWN"


@dataclass
class ZoneCfg:
    zone_id: str
    enabled: bool
    caution_m: float
    danger_m: float


@dataclass
class Config:
    zones: dict[str, ZoneCfg]
    sensor_to_zone: dict[str, str]
    zone_to_sensors: dict[str, list[str]]

    @property
    def zone_ids(self) -> list[str]:
        return [zid for zid, z in self.zones.items() if z.enabled]


def load_config(zones_path: Path, sensors_path: Path) -> Config:
    """Load zones + sensors config and build the reverse zone -> sensors index (FR-02/03)."""
    zc = json.loads(Path(zones_path).read_text(encoding="utf-8"))
    sc = json.loads(Path(sensors_path).read_text(encoding="utf-8"))
    defaults = zc.get("defaults", {})

    zones: dict[str, ZoneCfg] = {}
    for z in zc["zones"]:
        zones[z["id"]] = ZoneCfg(
            zone_id=z["id"],
            enabled=z.get("enabled", True),
            caution_m=float(z.get("caution_m", defaults.get("caution_m", 1.5))),
            danger_m=float(z.get("danger_m", defaults.get("danger_m", 0.8))),
        )

    sensor_to_zone: dict[str, str] = {}
    zone_to_sensors: dict[str, list[str]] = {zid: [] for zid in zones}
    for s in sc["sensors"]:
        if s.get("enabled", True) is False:
            continue  # e.g. the phase-2 camera (enabled:false)
        sid, zone = s["id"], s["zone"]
        sensor_to_zone[sid] = zone
        zone_to_sensors.setdefault(zone, []).append(sid)

    return Config(zones=zones, sensor_to_zone=sensor_to_zone, zone_to_sensors=zone_to_sensors)


def zone_severity(zone: ZoneCfg, readings: list[dict]) -> tuple[str, float | None]:
    """Severity for one zone from its contributing sensors' latest readings (05 §5.2).

    `readings` is the latest reading dict per contributing sensor.
    Returns (severity, nearest_range_m). S1 MVP: no debounce/context.
    """
    healthy = [r for r in readings if r.get("health", "ok") == "ok"]
    if not healthy:
        return UNKNOWN, None  # no healthy sensor reporting (NFR-04)
    present = [r for r in healthy if r.get("present") and r.get("range_m") is not None]
    if not present:
        return SAFE, None  # healthy but clear -- empty-present => SAFE (R2-6)
    nearest = min(float(r["range_m"]) for r in present)
    if nearest <= zone.danger_m:
        return DANGER, nearest
    if nearest <= zone.caution_m:
        return CAUTION, nearest
    return SAFE, nearest
