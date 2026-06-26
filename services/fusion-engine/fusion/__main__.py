"""Fusion engine — transport & loop.

Subscribes to bsw/sensor/#, bsw/detection/#, and bsw/vehicle; feeds them to the stateful
FusionEngine; on a fixed tick publishes retained bsw/zone/{zone_id} and logs severity
transitions (FR-10). Emits a ~1 Hz bsw/health/fusion heartbeat (ADR-0006 #2) with an MQTT
Last-Will (04 §4.3.5). Staleness uses a local monotonic clock (ADR-0008).

Run (from services/fusion-engine, with the broker up):
    python -m fusion
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from .engine import FusionEngine, load_config
from .eventlog import EventLog

REPO = Path(__file__).resolve().parents[3]
DEFAULT_ZONES = REPO / "config" / "zones.example.json"
DEFAULT_SENSORS = REPO / "config" / "sensors.example.json"

TICK_HZ = 10
HEARTBEAT_S = 1.0


def now_ms() -> int:
    return int(time.time() * 1000)


def mono_ms() -> float:
    return time.monotonic() * 1000.0


def make_client() -> mqtt.Client:
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        return mqtt.Client()


def health(status: str, detail: str) -> str:
    return json.dumps({"schema": "bsw.health/1", "component": "fusion",
                       "ts": now_ms(), "status": status, "detail": detail})


def main() -> None:
    ap = argparse.ArgumentParser(description="BSW fusion engine")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--zones", type=Path, default=DEFAULT_ZONES)
    ap.add_argument("--sensors", type=Path, default=DEFAULT_SENSORS)
    ap.add_argument("--log-dir", type=Path, default=REPO / "logs")
    args = ap.parse_args()

    cfg = load_config(args.zones, args.sensors)
    engine = FusionEngine(cfg)
    log = EventLog(args.log_dir)
    print(f"[fusion] {len(cfg.zone_ids)} zones, {len(cfg.sensor_to_zone)} sensors; logging -> {args.log_dir}")

    vehicle: dict | None = None
    last_sev: dict[str, str] = {}
    lock = threading.Lock()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"[fusion] connected ({reason_code})")
        client.subscribe([("bsw/sensor/#", 0), ("bsw/detection/#", 0), ("bsw/vehicle", 0)])
        client.publish("bsw/health/fusion", health("ok", "fusion up"), qos=0)

    def on_message(client, userdata, msg):
        nonlocal vehicle
        try:
            data = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        topic = msg.topic
        with lock:
            if topic == "bsw/vehicle":
                vehicle = data
            else:  # sensor or detection reading
                engine.ingest(data, mono_ms())

    client = make_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set("bsw/health/fusion", health("fault", "ungraceful disconnect (LWT)"), qos=1)
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    last_hb = 0.0
    try:
        while True:
            tick = time.time()
            with lock:
                veh = dict(vehicle) if vehicle else None
                states = engine.tick(mono_ms(), now_ms(), veh)
            for st in states:
                zid, sev = st["zone_id"], st["severity"]
                if last_sev.get(zid) != sev:
                    log.transition(st["ts"], zid, last_sev.get(zid, "-"), sev,
                                   st["nearest_range_m"], st["reason"])
                    last_sev[zid] = sev
                client.publish(f"bsw/zone/{zid}", json.dumps(st), qos=0, retain=True)
            if tick - last_hb >= HEARTBEAT_S:
                client.publish("bsw/health/fusion", health("ok", f"{len(engine.readings)} sensors seen"), qos=0)
                last_hb = tick
            time.sleep(max(0.0, 1.0 / TICK_HZ - (time.time() - tick)))
    except KeyboardInterrupt:
        print("\n[fusion] stopping")
    finally:
        log.close()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
