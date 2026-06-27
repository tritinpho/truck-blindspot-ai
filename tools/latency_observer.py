#!/usr/bin/env python3
"""Single-observer end-to-end latency measurement (ADR-0008 #3, NFR-01).

You cannot subtract an ESP32 publish-`ts` from an HMI render-`ts` — they are different, unsynced,
RTC-less clocks (ADR-0008). So this tap subscribes to BOTH the stimulus (bsw/sensor/#) and the
effect (bsw/zone/#) and timestamps each arrival with ITS OWN monotonic clock → a valid
single-clock delta. Per zone it arms when a reading first enters that zone's danger range and
fires when the zone's severity becomes DANGER. The pairing core is sim/metrics.LatencyPairer
(pure, unit-tested); this is the MQTT shell.

    docker compose -f deploy/docker-compose.yml up -d
    (cd services/fusion-engine && python -m fusion)
    python tools/latency_observer.py &        # start the tap
    python tools/scenario_runner.py S2 --live # drive a scenario; Ctrl-C the tap for the summary
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services" / "fusion-engine"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs on the Windows cp1252 console

from fusion.engine import load_config  # noqa: E402  (reuse the same sensor→zone + danger_m map)
from sim.metrics import LatencyPairer  # noqa: E402


def mono_ms() -> float:
    return time.monotonic() * 1000.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--zones", type=Path, default=REPO / "config" / "zones.example.json")
    ap.add_argument("--sensors", type=Path, default=REPO / "config" / "sensors.example.json")
    args = ap.parse_args()

    cfg = load_config(args.zones, args.sensors)
    danger_m = {zid: z.danger_m for zid, z in cfg.zones.items()}
    pairer = LatencyPairer()

    import paho.mqtt.client as mqtt

    def on_connect(client, *_):
        client.subscribe([("bsw/sensor/#", 0), ("bsw/zone/#", 0)])
        print("[latency] observing bsw/sensor/# (stimulus) + bsw/zone/# (effect); Ctrl-C for summary")

    def on_message(client, userdata, msg):
        now = mono_ms()  # the observer's OWN clock for both stimulus and effect (ADR-0008 #3)
        try:
            data = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        parts = msg.topic.split("/")
        if parts[1] == "sensor":
            sid = data.get("sensor_id", parts[-1])
            zone = cfg.sensor_to_zone.get(sid)
            rng = data.get("range_m")
            if zone and data.get("present") and rng is not None and rng <= danger_m.get(zone, 0):
                pairer.stimulus(zone, now)
        elif parts[1] == "zone":
            pairer.effect(data.get("zone_id", parts[-1]), data.get("severity", ""), now)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(args.host, args.port, 30)
    except OSError as e:
        print(f"[latency] broker unreachable at {args.host}:{args.port} ({e})", file=sys.stderr)
        return
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # print the summary + disconnect on ANY exit (Ctrl-C OR a dropped connection), not only on
        # KeyboardInterrupt — otherwise loop_forever() returning would leak the socket silently.
        s = pairer.summary()
        print("\n[latency] danger-path end-to-end (single observer clock):")
        if s["n"] == 0:
            print("   no danger-path events observed")
        else:
            print(f"   n={s['n']}  min={s['min']:.0f}  p50={s['p50']:.0f}  mean={s['mean']:.0f}  "
                  f"p95={s['p95']:.0f}  max={s['max']:.0f}  ms   "
                  f"(NFR-01 danger-path target <= 200 ms; tail/L4 bench is headline)")
        client.disconnect()


if __name__ == "__main__":
    main()
