"""Geometric sensor-emulation for the simulator (08 §8.2-8.3).

Pure — no MQTT, no fusion dependency. Objects live in the normalized top-view plane (the same
0..1 frame as config/zones.example.json). For each configured sensor this module decides whether
an object falls in the sensor's zone (point-in-polygon) and at what range (distance to the truck
body, scaled to metres), then emits the SAME wire messages a real rig publishes (parity,
ADR-0005): bsw.sensor_reading for ultrasonic, bsw.detection for a camera. Optional seeded noise,
dropout, and the ADR-0007 group-fire schedule let the L3 suite stress debounce/staleness.

CAVEAT (11 §11.2, 14 §P2 #6): detection here is derived from zone geometry, so the sim measures
the model against itself. L3 validates *logic and regression*; the headline detection/latency
figures must come from L4 bench, never from this module.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from random import Random

# Default real truck width (m) spanning the truck-outline width in the normalized frame; sets the
# metres-per-normalized-unit scale so example-config ranges land in sensible blind-spot distances.
DEFAULT_TRUCK_WIDTH_M = 2.5


@dataclass
class Obj:
    """A scene object at a normalized (x, y); `cls` is its class (camera/phase-2 only)."""
    x: float
    y: float
    cls: str | None = None


@dataclass
class SensorGeom:
    sensor_id: str
    zone: str
    modality: str
    max_range_m: float
    fire_group: int


# ------------------------------------------------------------------ planar geometry helpers

def point_in_poly(x: float, y: float, poly: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon (even-odd rule)."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _dist_point_seg(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_to_poly(x: float, y: float, poly: list[list[float]]) -> float:
    """Min distance from a point to a polygon boundary (0 if the point is inside)."""
    if point_in_poly(x, y, poly):
        return 0.0
    n = len(poly)
    return min(_dist_point_seg(x, y, *poly[i], *poly[(i + 1) % n]) for i in range(n))


def nearest_point_on_poly(x: float, y: float, poly: list[list[float]]) -> tuple[float, float]:
    """Closest boundary point — used to place objects at a target distance from the truck."""
    best, bd = (poly[0][0], poly[0][1]), float("inf")
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            cx, cy = ax, ay
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            cx, cy = ax + t * dx, ay + t * dy
        d = math.hypot(x - cx, y - cy)
        if d < bd:
            best, bd = (cx, cy), d
    return best


# --------------------------------------------------------------------------- the sim

class Sim:
    """Top-view geometric model built from the same config the fusion engine loads."""

    def __init__(self, zones: dict[str, list[list[float]]], truck_outline: list[list[float]],
                 sensors: list[SensorGeom], truck_width_m: float = DEFAULT_TRUCK_WIDTH_M):
        self.zones = zones
        self.truck_outline = truck_outline
        self.sensors = sensors
        xs = [p[0] for p in truck_outline]
        truck_width_norm = (max(xs) - min(xs)) or 1.0
        self.mpu = truck_width_m / truck_width_norm  # metres per normalized unit

    @classmethod
    def from_config(cls, zones_path: Path, sensors_path: Path,
                    truck_width_m: float = DEFAULT_TRUCK_WIDTH_M,
                    include_disabled: bool = False) -> "Sim":
        zc = json.loads(Path(zones_path).read_text(encoding="utf-8"))
        sc = json.loads(Path(sensors_path).read_text(encoding="utf-8"))
        zones = {z["id"]: z["polygon_norm"] for z in zc["zones"]}
        sensors = []
        for s in sc["sensors"]:
            if "id" not in s:
                continue  # skip the $comment-only entry
            if s.get("enabled", True) is False and not include_disabled:
                continue
            sensors.append(SensorGeom(
                sensor_id=s["id"], zone=s["zone"], modality=s.get("modality", "ultrasonic"),
                max_range_m=float(s.get("max_range_m", 4.0)), fire_group=int(s.get("fire_group", 0)),
            ))
        return cls(zones, zc["truck_outline_norm"], sensors, truck_width_m)

    # --- forward: position → zone + range ---

    def classify(self, x: float, y: float) -> str | None:
        for zid, poly in self.zones.items():
            if point_in_poly(x, y, poly):
                return zid
        return None

    def range_m(self, x: float, y: float) -> float:
        return dist_to_poly(x, y, self.truck_outline) * self.mpu

    # --- inverse: zone + desired range → a placeable position (for authoring scenarios) ---

    def place_in_zone(self, zone_id: str, range_m: float) -> Obj:
        """A point inside `zone_id` ~`range_m` metres from the truck, along the outward normal."""
        poly = self.zones[zone_id]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        nx, ny = nearest_point_on_poly(cx, cy, self.truck_outline)
        dx, dy = cx - nx, cy - ny
        d = math.hypot(dx, dy) or 1.0
        step = range_m / self.mpu
        return Obj(nx + dx / d * step, ny + dy / d * step)

    # --- emit wire messages for a scene ---

    def readings_at(self, objs: list[Obj], ts: int, *, tick: int = 0, group_fire: bool = True,
                    noise_m: float = 0.0, dropout: float = 0.0, rng: Random | None = None) -> list[dict]:
        """One message per *firing* sensor for the current scene. Ultrasonic → sensor_reading,
        camera → detection. group_fire alternates the two fire groups (ADR-0007: ~master/2 each)."""
        rng = rng or Random(0)
        msgs: list[dict] = []
        for s in self.sensors:
            if group_fire and s.fire_group != (tick % 2):
                continue  # not this sensor's turn to fire
            in_zone = [o for o in objs if self.classify(o.x, o.y) == s.zone]
            if s.modality == "camera":
                classified = [o for o in in_zone if o.cls]
                if classified:
                    o = min(classified, key=lambda o: self.range_m(o.x, o.y))
                    msgs.append(self._detection(s, o, ts))
                continue
            # ultrasonic: nearest in-range object, else clear
            present = [o for o in in_zone if self.range_m(o.x, o.y) <= s.max_range_m]
            if present and dropout and rng.random() < dropout:
                continue  # dropped frame → fusion ages it toward UNKNOWN
            if present:
                o = min(present, key=lambda o: self.range_m(o.x, o.y))
                rng_m = max(0.0, round(self.range_m(o.x, o.y) + (rng.gauss(0, noise_m) if noise_m else 0), 3))
                msgs.append(self._reading(s, True, rng_m, ts))
            else:
                msgs.append(self._reading(s, False, None, ts))
        return msgs

    def _reading(self, s: SensorGeom, present: bool, rng_m: float | None, ts: int) -> dict:
        return {
            "schema": "bsw.sensor_reading/1", "sensor_id": s.sensor_id, "ts": ts,
            "ts_kind": "epoch_ms", "modality": "ultrasonic", "present": present,
            "range_m": rng_m, "confidence": 0.9, "health": "ok",
        }

    def _detection(self, s: SensorGeom, o: Obj, ts: int) -> dict:
        # est_range_m is emitted for contract-completeness (schemas/detection) and any future L4
        # camera-ranging work, but the phase-1/2 fusion engine does NOT consume it — it reads only
        # object_class from a detection and ranges from the co-located ultrasonic (engine._update_zone).
        return {
            "schema": "bsw.detection/1", "sensor_id": s.sensor_id, "ts": ts,
            "ts_kind": "epoch_ms", "object_class": o.cls, "confidence": 0.8,
            "est_range_m": round(self.range_m(o.x, o.y), 3),
        }
