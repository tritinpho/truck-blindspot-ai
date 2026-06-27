"""Fusion engine — MQTT transport & real-time loop.

Thin paho wrapper around `FusionService` (service.py), which holds all the broker-agnostic
routing/tick logic. This module only owns the things that need a real broker and a wall clock:
the client, the subscribe set, the LWT, the ~1 Hz heartbeat, and the fixed-cadence publish loop.

Subscribes bsw/sensor/#, bsw/detection/#, bsw/vehicle, and bsw/cmd/# (live retune — set_threshold
/ enable_zone / disable_zone / reload_config, 04 §4.3.6). On each tick publishes retained
bsw/zone/{zone_id} and logs severity transitions (FR-10). Emits a bsw/health/fusion heartbeat with
an MQTT Last-Will (04 §4.3.5, ADR-0006 #2). Staleness uses a local monotonic clock (ADR-0008).

Run (from services/fusion-engine, with the broker up):
    python -m fusion
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from .engine import load_config
from .eventlog import EventLog
from .service import SUB_TOPICS, FusionService

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
    log = EventLog(args.log_dir)
    svc = FusionService(cfg, log=log, zones_path=args.zones, sensors_path=args.sensors)
    print(f"[fusion] {len(cfg.zone_ids)} zones, {len(cfg.sensor_to_zone)} sensors; logging -> {args.log_dir}")

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"[fusion] connected ({reason_code})")
        client.subscribe(SUB_TOPICS)
        client.publish("bsw/health/fusion", health("ok", "fusion up"), qos=0)

    def on_message(client, userdata, msg):
        res = svc.handle_message(msg.topic, msg.payload, mono_ms(), now_ms())
        if res is not None:
            op, applied, detail = res
            print(f"[fusion] cmd {op}: {'applied' if applied else 'rejected'} — {detail}")

    client = make_client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set("bsw/health/fusion", health("fault", "ungraceful disconnect (LWT)"), qos=1)
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    last_hb = 0.0
    tick_fails = 0
    try:
        while True:
            tick = time.time()
            # A tick must never kill the loop: a wedged fusion stops the zone stream, and the HMI
            # freshness clock then degrades the map to UNKNOWN (ADR-0006) — a visible fault, not a
            # frozen-green one. Readings are sanitized at ingest, but this guard is the backstop for
            # any other unexpected input so the central safety service keeps running.
            try:
                states, _ = svc.collect_tick(mono_ms(), now_ms())
                for st in states:
                    client.publish(f"bsw/zone/{st['zone_id']}", json.dumps(st), qos=0, retain=True)
                tick_fails = 0
            except Exception as e:  # noqa: BLE001 — last-resort liveness guard
                tick_fails += 1
                print(f"[fusion] tick error (continuing): {e!r}")
            if tick - last_hb >= HEARTBEAT_S:
                # The heartbeat must reflect tick health. If ticks are persistently failing the zone
                # stream is stalled, so a steady "ok" heartbeat would keep the HMI in MONITORING on a
                # frozen map — exactly the failure ADR-0006 forbids. Publish a fault instead so the
                # HMI trips SIGNAL_LOST. (One stray tick error still heartbeats ok.)
                if tick_fails >= 3:
                    client.publish("bsw/health/fusion",
                                   health("fault", f"tick failing ({tick_fails} consecutive)"), qos=0)
                else:
                    client.publish("bsw/health/fusion",
                                   health("ok", f"{svc.sensors_seen()} sensors seen"), qos=0)
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
