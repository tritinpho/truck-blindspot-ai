#!/usr/bin/env python3
"""S0 smoke test: publish one sample sensor reading to the broker (build-plan S0 DoD).

Proves the contract end-to-end on a running broker:
    docker compose -f deploy/docker-compose.yml up -d
    python tools/publish_sample.py            # -> bsw/sensor/right_mid

Subscribe to watch it:  mosquitto_sub -t 'bsw/#' -v   (or the HMI skeleton's console).
"""
from __future__ import annotations

import argparse
import json
import time


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--sensor", default="right_mid")
    ap.add_argument("--range", type=float, default=None,
                    help="range_m for a present reading; omit for a 'not present' (clear) reading")
    args = ap.parse_args()

    import paho.mqtt.publish as publish  # pip install paho-mqtt

    present = args.range is not None
    msg = {
        "schema": "bsw.sensor_reading/1",
        "sensor_id": args.sensor,
        "ts": int(time.time() * 1000),
        "ts_kind": "epoch_ms",
        "modality": "ultrasonic",
        "present": present,
        "range_m": args.range if present else None,
        "confidence": 0.9,
        "health": "ok",
    }
    topic = f"bsw/sensor/{args.sensor}"
    publish.single(topic, json.dumps(msg), hostname=args.host, port=args.port, qos=0)
    print(f"published -> {topic}: {msg}")


if __name__ == "__main__":
    main()
