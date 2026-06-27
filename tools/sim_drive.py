#!/usr/bin/env python3
"""S1 vertical-slice driver: a scripted approaching/retreating object on one sensor.

Publishes bsw/sensor/right_mid readings that sweep 3.0 m -> 0.5 m -> 3.0 m, so the RIGHT
zone walks SAFE -> CAUTION -> DANGER -> CAUTION -> SAFE in the HMI (RIGHT thresholds in
config: caution 1.8 m, danger 1.0 m). The interactive scene editor lands in S2/S4; this
headless driver is enough to prove the end-to-end thread.

    docker compose -f deploy/docker-compose.yml up -d
    (cd services/fusion-engine && python -m fusion)
    python tools/sim_drive.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--sensor", default="right_mid")
    ap.add_argument("--period", type=float, default=0.2, help="seconds between readings (~5 Hz)")
    args = ap.parse_args()

    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    try:
        client.connect(args.host, args.port, 30)
    except OSError as e:
        print(f"[sim] broker unreachable at {args.host}:{args.port} ({e})", file=sys.stderr)
        return
    client.loop_start()

    down = [round(x / 10, 2) for x in range(30, 4, -1)]  # 3.0 .. 0.5
    sweep = down + list(reversed(down))
    topic = f"bsw/sensor/{args.sensor}"
    print(f"[sim] driving {topic} (Ctrl-C to stop)")
    try:
        for rng in itertools.cycle(sweep):
            msg = {
                "schema": "bsw.sensor_reading/1", "sensor_id": args.sensor,
                "ts": int(time.time() * 1000), "ts_kind": "epoch_ms",
                "modality": "ultrasonic", "present": True, "range_m": rng,
                "confidence": 0.9, "health": "ok",
            }
            client.publish(topic, json.dumps(msg), qos=0)
            print(f"  range_m = {rng:>4}  ", end="\r")
            time.sleep(args.period)
    except KeyboardInterrupt:
        print("\n[sim] stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
