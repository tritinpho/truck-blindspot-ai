#!/usr/bin/env python3
"""S3 demo driver — a scripted timeline that exercises the whole in-cabin HMI.

Where `sim_drive.py` is the S1 one-sensor sweep, this plays a multi-zone scenario so the full
S3 HMI is demoable end-to-end: zone tints, object icons, the primary-alert banner, escalating
audio, context boost, park-standby (visual alert with audio suppressed), and a sensor dropout
that drives a zone to UNKNOWN + the fault chime — all on the SAME contracts a real rig emits
(bsw/sensor/{id} + bsw/vehicle), so sim/real parity holds (ADR-0005).

Every tick it publishes a reading for ALL eight ultrasonic sensors — present=false (clear) for
idle ones, present=true with a range for the active one(s) — so idle zones read SAFE (not
UNKNOWN) exactly like a continuously-firing rig. A "dropout" phase simply stops publishing one
sensor; fusion then ages it past stale_after_ms and the zone goes UNKNOWN (fail-loud, NFR-04).

    python tools/demo.py               # one command: compose up (+HMI :8080) → open browser → this timeline
    # …or by hand, with the stack already up (broker + fusion run in the compose stack):
    docker compose -f deploy/docker-compose.yml --profile hmi up -d   # broker + fusion + HMI at :8080
    python tools/sim_demo.py                                          # drive this timeline

Tip: kill fusion mid-run (`docker compose -f deploy/docker-compose.yml kill fusion`) to see the map
flip to UNKNOWN + SIGNAL LOST within the freshness window (TC-F4); start the HMI before fusion to see
the "warming up — not yet monitoring" screen (NFR-12).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs (▶) on a Windows cp1252 console

# zone -> the ultrasonic sensor that feeds it (mirrors config/sensors.example.json)
ZONE_SENSOR = {
    "FRONT": "front_center", "FRONT_LEFT": "front_left", "FRONT_RIGHT": "front_right",
    "LEFT": "left_mid", "RIGHT": "right_mid",
    "REAR_LEFT": "rear_left", "REAR_RIGHT": "rear_right", "REAR": "rear_center",
}
ALL_SENSORS = list(ZONE_SENSOR.values())

NONE_VEH = {"gear": "drive", "speed_kph": 6.0, "turn_signal": "none"}


def ramp(t: float, a: float, b: float) -> float:
    """Linear a->b as t goes 0..1 (an object approaching, or retreating)."""
    t = max(0.0, min(1.0, t))
    return round(a + (b - a) * t, 2)


# A phase = (label, seconds, vehicle_context, active, dropped)
#   active: zone -> ("approach"|"hold", start_m, end_m)   (range over the phase)
#   dropped: sensors to STOP publishing this phase (→ stale → UNKNOWN)
PHASES = [
    ("S1 pull-away — motorbike in FRONT", 6.0, NONE_VEH,
     {"FRONT": ("approach", 3.0, 0.4)}, set()),
    ("clear", 2.0, NONE_VEH, {}, set()),
    ("S2 RIGHT TURN — motorbike squeezing along RIGHT (signal=right, boosted)", 6.0,
     {"gear": "drive", "speed_kph": 9.0, "turn_signal": "right"},
     {"RIGHT": ("approach", 2.6, 0.5), "FRONT_RIGHT": ("approach", 2.4, 0.9)}, set()),
    ("FAULT — RIGHT ultrasonic unplugged (→ UNKNOWN + fault chime)", 3.5,
     {"gear": "drive", "speed_kph": 9.0, "turn_signal": "right"},
     {"RIGHT": ("hold", 0.5, 0.5), "FRONT_RIGHT": ("hold", 0.9, 0.9)}, {"right_mid"}),
    ("clear", 2.0, NONE_VEH, {}, set()),
    ("S4 reversing — pallet behind on REAR (gear=reverse, boosted)", 5.0,
     {"gear": "reverse", "speed_kph": 3.0, "turn_signal": "none"},
     {"REAR": ("approach", 1.8, 0.4)}, set()),
    ("clear", 2.0, NONE_VEH, {}, set()),
    ("S6 parked by a wall on LEFT (gear=park, standby → visual only, audio muted)", 6.0,
     {"gear": "park", "speed_kph": 0.0, "turn_signal": "none"},
     {"LEFT": ("hold", 0.5, 0.5)}, set()),
    ("clear", 2.0, NONE_VEH, {}, set()),
]


def sensor_msg(sid: str, present: bool, rng: float | None) -> str:
    return json.dumps({
        "schema": "bsw.sensor_reading/1", "sensor_id": sid,
        "ts": int(time.time() * 1000), "ts_kind": "epoch_ms",
        "modality": "ultrasonic", "present": present,
        "range_m": rng if present else None,
        "confidence": 0.9, "health": "ok",
    })


def vehicle_msg(veh: dict) -> str:
    return json.dumps({
        "schema": "bsw.vehicle/1", "ts": int(time.time() * 1000), "ts_kind": "epoch_ms",
        **veh,
    })


def drive(host: str = "localhost", port: int = 1883, hz: float = 12.0, once: bool = False) -> int:
    """Play the narrated multi-zone timeline live onto the broker. Returns 0 on clean finish / Ctrl-C,
    1 on a bad rate or an unreachable broker. Importable so `tools/demo.py` reuses the same timeline
    instead of duplicating it (one source of truth for the demo content)."""
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    # Compute the period BEFORE connecting (a bad hz of 0 would ZeroDivisionError after loop_start,
    # leaking the network thread). Guard the zero so it fails cleanly here.
    if hz <= 0:
        print(f"[demo] --hz must be > 0 (got {hz})", file=sys.stderr)
        return 1
    period = 1.0 / hz
    try:
        client.connect(host, port, 30)
    except OSError as e:
        print(f"[demo] broker unreachable at {host}:{port} ({e})", file=sys.stderr)
        return 1
    client.loop_start()

    print(f"[demo] driving {len(ALL_SENSORS)} sensors @ {hz:g} Hz "
          f"({'one pass' if once else 'looping'}; Ctrl-C to stop)")

    try:
        first = True
        while first or not once:
            first = False
            for label, dur, veh, active, dropped in PHASES:
                print(f"[demo] ▶ {label}")
                # resolve each active zone to its sensor
                act = {ZONE_SENSOR[z]: spec for z, spec in active.items()}
                t0 = time.time()
                while (elapsed := time.time() - t0) < dur:
                    frac = elapsed / dur
                    client.publish("bsw/vehicle", vehicle_msg(veh), qos=0)
                    for sid in ALL_SENSORS:
                        if sid in dropped:
                            continue  # silent → fusion ages it to UNKNOWN
                        spec = act.get(sid)
                        if spec is None:
                            client.publish(f"bsw/sensor/{sid}", sensor_msg(sid, False, None), qos=0)
                        else:
                            mode, a, b = spec
                            rng = ramp(frac, a, b) if mode == "approach" else round(b, 2)
                            client.publish(f"bsw/sensor/{sid}", sensor_msg(sid, True, rng), qos=0)
                    time.sleep(period)
        print("[demo] done")
    except KeyboardInterrupt:
        print("\n[demo] stopping")
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--hz", type=float, default=12.0, help="publish rate per sensor")
    ap.add_argument("--once", action="store_true", help="play the timeline once, then stop")
    args = ap.parse_args()
    raise SystemExit(drive(args.host, args.port, args.hz, args.once))


if __name__ == "__main__":
    main()
