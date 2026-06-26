"""Fusion engine — S1 MVP transport & loop.

Subscribes to bsw/sensor/#, keeps the latest reading per sensor, and on a fixed tick
recomputes per-zone severity (engine.zone_severity) and publishes retained
bsw/zone/{zone_id}. Emits a ~1 Hz bsw/health/fusion heartbeat (ADR-0006 #2) and registers
an MQTT Last-Will so the broker announces an ungraceful death immediately (04 §4.3.5).

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

from .engine import UNKNOWN, load_config, zone_severity

REPO = Path(__file__).resolve().parents[3]
DEFAULT_ZONES = REPO / "config" / "zones.example.json"
DEFAULT_SENSORS = REPO / "config" / "sensors.example.json"

TICK_HZ = 10
HEARTBEAT_S = 1.0


def now_ms() -> int:
    return int(time.time() * 1000)


def make_client() -> mqtt.Client:
    # paho 2.x requires an explicit callback API version; fall back for 1.x.
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        return mqtt.Client()


def health(status: str, detail: str) -> str:
    return json.dumps({
        "schema": "bsw.health/1", "component": "fusion",
        "ts": now_ms(), "status": status, "detail": detail,
    })


def main() -> None:
    ap = argparse.ArgumentParser(description="BSW fusion engine (S1 MVP)")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--zones", type=Path, default=DEFAULT_ZONES)
    ap.add_argument("--sensors", type=Path, default=DEFAULT_SENSORS)
    args = ap.parse_args()

    cfg = load_config(args.zones, args.sensors)
    print(f"[fusion] loaded {len(cfg.zone_ids)} zones, {len(cfg.sensor_to_zone)} sensors")

    latest: dict[str, dict] = {}
    lock = threading.Lock()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"[fusion] connected ({reason_code}); subscribing bsw/sensor/#")
        client.subscribe("bsw/sensor/#", qos=0)
        client.publish("bsw/health/fusion", health("ok", "fusion up"), qos=0)

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        sid = data.get("sensor_id")
        if sid in cfg.sensor_to_zone:
            with lock:
                latest[sid] = data

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
                snap = dict(latest)
            for zid in cfg.zone_ids:
                zone = cfg.zones[zid]
                readings = [snap[s] for s in cfg.zone_to_sensors.get(zid, []) if s in snap]
                sev, nearest = zone_severity(zone, readings) if readings else (UNKNOWN, None)
                payload = {
                    "schema": "bsw.zone_state/1", "zone_id": zid, "ts": now_ms(),
                    "severity": sev, "nearest_range_m": nearest, "source": "fusion",
                    "stale": sev == UNKNOWN,
                }
                client.publish(f"bsw/zone/{zid}", json.dumps(payload), qos=0, retain=True)
            if tick - last_hb >= HEARTBEAT_S:
                client.publish("bsw/health/fusion", health("ok", f"{len(snap)} sensors seen"), qos=0)
                last_hb = tick
            time.sleep(max(0.0, 1.0 / TICK_HZ - (time.time() - tick)))
    except KeyboardInterrupt:
        print("\n[fusion] stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
