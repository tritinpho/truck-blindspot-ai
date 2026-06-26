"""Fusion transport core — broker-agnostic.

`FusionService` is everything the fusion engine does *between* the wire and the engine, with **no
MQTT dependency**: it routes an incoming (topic, payload) to the right place (vehicle context /
sensor+detection readings / bsw/cmd), and on each tick produces the retained `bsw/zone/{id}`
payloads plus the severity-transition log rows. `__main__.py` wraps it in a paho client + a
real-time loop; the integration shim drives the SAME object over a loopback bus on a controlled
clock (tests/_loopback.py). One code path serves both — sim/real parity at the transport seam too
(ADR-0005), and the routing logic becomes unit-testable without a broker.

Clock discipline (ADR-0008): the caller stamps each ingest with a LOCAL monotonic ms clock; the
service never trusts a message `ts` for staleness.
"""
from __future__ import annotations

import json
import threading

from .engine import Config, FusionEngine, load_config
from .eventlog import EventLog

# What the fusion engine subscribes to. cmd is QoS 1 (config/commands, 04 §4.1); the rest QoS 0.
SUB_TOPICS = [("bsw/sensor/#", 0), ("bsw/detection/#", 0), ("bsw/vehicle", 0), ("bsw/cmd/#", 1)]

# Transition row: (ts, zone_id, from_sev, to_sev, nearest_range_m, reason)
Transition = tuple


class FusionService:
    def __init__(self, cfg: Config, log: EventLog | None = None,
                 zones_path=None, sensors_path=None):
        self.engine = FusionEngine(cfg)
        self.log = log
        self.zones_path = zones_path      # kept so reload_config can re-read from disk
        self.sensors_path = sensors_path
        self.vehicle: dict | None = None
        self.last_sev: dict[str, str] = {}
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ inbound routing

    def handle_message(self, topic: str, payload, arrival_mono_ms: float,
                       now_epoch_ms: int | None = None) -> tuple[str, bool, str] | None:
        """Route one wire message. Returns a (op, applied, detail) tuple iff it was a bsw/cmd
        (so the transport can surface it), else None. Malformed JSON is dropped (fail-safe)."""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        parts = topic.split("/")
        with self.lock:
            if topic == "bsw/vehicle":
                self.vehicle = data
                return None
            if len(parts) >= 2 and parts[1] == "cmd":
                return self._apply_cmd(data, now_epoch_ms)
            # sensor or detection reading
            self.engine.ingest(data, arrival_mono_ms)
            return None

    def _apply_cmd(self, data: dict, now_epoch_ms: int | None) -> tuple[str, bool, str]:
        op = data.get("op", "")
        args = data.get("args") or {}
        if op == "reload_config":
            applied, detail = self._reload()
        else:
            applied, detail = self.engine.apply_cmd(op, args)
        if self.log is not None:
            self.log.command(now_epoch_ms if now_epoch_ms is not None else data.get("ts", 0),
                             op, applied, detail)
        return op, applied, detail

    def _reload(self) -> tuple[bool, str]:
        if not (self.zones_path and self.sensors_path):
            return False, "reload_config: no config paths"
        try:
            cfg = load_config(self.zones_path, self.sensors_path)
        except Exception as e:  # bad edit on disk — keep running the last-good config (fail-safe)
            return False, f"reload_config failed: {e}"
        self.engine.replace_config(cfg)
        return True, f"reloaded {len(cfg.zone_ids)} zones, {len(cfg.sensor_to_zone)} sensors"

    # ------------------------------------------------------------------ outbound (per tick)

    def collect_tick(self, now_mono_ms: float, now_epoch_ms: int,
                     ) -> tuple[list[dict], list[Transition]]:
        """Advance one tick: returns (zone payloads to publish retained, transitions since last
        tick). Transitions are also written to the event log here, so logging has one home."""
        with self.lock:
            veh = dict(self.vehicle) if self.vehicle else None
            states = self.engine.tick(now_mono_ms, now_epoch_ms, veh)
        transitions: list[Transition] = []
        for st in states:
            zid, sev = st["zone_id"], st["severity"]
            if self.last_sev.get(zid) != sev:
                row = (st["ts"], zid, self.last_sev.get(zid, "-"), sev,
                       st["nearest_range_m"], st["reason"])
                transitions.append(row)
                self.last_sev[zid] = sev
                if self.log is not None:
                    self.log.transition(*row)
        return states, transitions

    def sensors_seen(self) -> int:
        return len(self.engine.readings)
