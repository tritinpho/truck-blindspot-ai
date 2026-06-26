"""Deterministic scenario runner — the heart of the L3 suite (11 §11.2).

Drives the real `FusionEngine` (the same code the live service runs) with geometry-produced
readings on a CONTROLLED clock: the tick index supplies both the monotonic arrival time and the
wire `ts`, so a run is fully reproducible — no broker, no wall-clock, no timing flake. The
returned Timeline exposes the zone-severity history plus the HMI-side priority/audio policy
(mirrors apps/hmi select.ts) so a scenario can assert what the driver would see and hear.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "fusion-engine"))

from fusion.engine import Config, FusionEngine, load_config  # noqa: E402

from .geometry import Sim  # noqa: E402
from .scenarios import Scenario  # noqa: E402

DEFAULT_ZONES = REPO / "config" / "zones.example.json"
DEFAULT_SENSORS = REPO / "config" / "sensors.example.json"


def _rank(sev: str) -> int:
    return 2 if sev == "DANGER" else 1 if sev == "CAUTION" else 0


@dataclass
class Timeline:
    cfg: Config
    ticks: list[dict] = field(default_factory=list)  # [{t, states:{zone:state}}]

    def add(self, t: int, states: dict) -> None:
        self.ticks.append({"t": t, "states": states})

    def severities(self, zone: str) -> list[str]:
        return [tk["states"][zone]["severity"] for tk in self.ticks]

    def final(self, zone: str) -> str:
        return self.ticks[-1]["states"][zone]["severity"]

    def reached(self, zone: str, sev: str) -> bool:
        return sev in self.severities(zone)

    def first_tick(self, zone: str, sev: str) -> int | None:
        for tk in self.ticks:
            if tk["states"][zone]["severity"] == sev:
                return tk["t"]
        return None

    def transitions(self, zone: str) -> int:
        s = self.severities(zone)
        return sum(1 for a, b in zip(s, s[1:]) if a != b)

    def _states_at(self, t: int | None) -> dict:
        tk = self.ticks[-1] if t is None else next(x for x in self.ticks if x["t"] == t)
        return tk["states"]

    def standby(self, t: int | None = None) -> bool:
        return any(s.get("standby") for s in self._states_at(t).values())

    def worst_zone(self, t: int | None = None) -> str | None:
        """Highest risk_weight × severity among actively-alerting zones (05 §5.6)."""
        best, best_score, best_rank = None, 0.0, 0
        for zid, s in self._states_at(t).items():
            rank = _rank(s["severity"])
            if rank == 0:
                continue
            score = self.cfg.zones[zid].risk_weight * rank
            if score > best_score or (score == best_score and rank > best_rank):
                best, best_score, best_rank = zid, score, rank
        return best

    def audio_target(self, t: int | None = None) -> str:
        """Single worst severity to sound; park-standby suppresses audio (05 §5.5)."""
        if self.standby(t):
            return "SILENT"
        worst = max((_rank(s["severity"]) for s in self._states_at(t).values()), default=0)
        return "DANGER" if worst == 2 else "CAUTION" if worst == 1 else "SILENT"


def build(zones_path: Path = DEFAULT_ZONES, sensors_path: Path = DEFAULT_SENSORS,
          enable_camera: bool = False) -> tuple[Sim, Config]:
    sim = Sim.from_config(zones_path, sensors_path, include_disabled=enable_camera)
    cfg = load_config(zones_path, sensors_path)
    if enable_camera:
        # phase-2: register the camera sensor(s) the fusion config skipped (enabled:false) so the
        # engine consumes their detections (object_class) alongside the ultrasonic range.
        for s in sim.sensors:
            if s.sensor_id not in cfg.sensor_to_zone:
                cfg.sensor_to_zone[s.sensor_id] = s.zone
                cfg.zone_to_sensors.setdefault(s.zone, []).append(s.sensor_id)
    return sim, cfg


def scenario_tick_messages(sim: Sim, scenario: Scenario, tick: int, dt_ms: int, ts: int,
                           rng: Random | None = None) -> list[tuple[str, dict]]:
    """The (topic, payload) wire stream for ONE tick of a scenario — the exact messages a real rig
    (or `scenario_runner.py --live`) puts on the bus: a bsw/vehicle (when the scenario sets
    context) plus one bsw/sensor / bsw/detection per firing sensor, with unplugged sensors filtered
    out (TC-F1). Shared by the live publisher and the integration shim so there is ONE wire stream,
    not two (parity, ADR-0005). `ts` only stamps the payload (display); fusion ages from local
    arrival (ADR-0008), so the caller's clock choice does not change outcomes."""
    t = tick * dt_ms
    msgs: list[tuple[str, dict]] = []
    if scenario.vehicle is not None:
        msgs.append(("bsw/vehicle",
                     {"schema": "bsw.vehicle/1", "ts": ts, "ts_kind": "epoch_ms", **scenario.vehicle}))
    dropped = scenario.dropped_at(t)
    for m in sim.readings_at(scenario.objects_at(sim, t), ts=ts, tick=tick,
                             group_fire=scenario.group_fire, noise_m=scenario.noise_m,
                             dropout=scenario.dropout, rng=rng):
        if m["sensor_id"] in dropped:
            continue
        topic = "bsw/detection/" if m["schema"].startswith("bsw.detection") else "bsw/sensor/"
        msgs.append((topic + m["sensor_id"], m))
    return msgs


def run(scenario: Scenario, dt_ms: int = 100,
        zones_path: Path = DEFAULT_ZONES, sensors_path: Path = DEFAULT_SENSORS) -> Timeline:
    sim, cfg = build(zones_path, sensors_path, enable_camera=scenario.enable_camera)
    eng = FusionEngine(cfg)
    rng = Random(scenario.seed)
    tl = Timeline(cfg)

    n = scenario.duration_ms // dt_ms
    for tick in range(n + 1):
        t = tick * dt_ms
        dropped = scenario.dropped_at(t)
        for m in sim.readings_at(scenario.objects_at(sim, t), ts=t, tick=tick,
                                 group_fire=scenario.group_fire, noise_m=scenario.noise_m,
                                 dropout=scenario.dropout, rng=rng):
            if m["sensor_id"] in dropped:
                continue  # TC-F1: sensor unplugged → fusion ages it to UNKNOWN
            eng.ingest(m, float(t))
        states = {s["zone_id"]: s for s in eng.tick(float(t), t, scenario.vehicle)}
        tl.add(t, states)
    return tl
