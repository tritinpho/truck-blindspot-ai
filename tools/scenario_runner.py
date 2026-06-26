#!/usr/bin/env python3
"""Scenario runner — replay S1-S6 (+ fault cases) deterministically, or publish them live.

Two modes, one scenario source (sim/scenarios.py), same wire contract a real rig emits (parity,
ADR-0005):

  * default (deterministic): drive the real fusion engine in-process on a controlled clock and
    print each scenario's outcome. No broker. This is what the L3 CI suite asserts on
    (tests/test_scenarios.py).
  * --live: publish the scenario's bsw/sensor + bsw/vehicle messages to the broker in real time,
    so the running fusion engine + HMI react — a geometry-driven alternative to sim_demo.py.

    python tools/scenario_runner.py                 # run every scenario, print summaries
    python tools/scenario_runner.py S2 -v           # one scenario, tick-by-tick
    python tools/scenario_runner.py S2 --live        # publish S2 to the broker (broker+fusion up)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs on the Windows cp1252 console

import sim  # noqa: E402
from sim.runner import build  # noqa: E402

TOUCHED_ONLY = True


def summarize(sc, verbose: bool) -> None:
    tl = sim.run(sc)
    zones = sorted({tr.zone for tr in sc.tracks})
    finals = {z: tl.final(z) for z in zones}
    print(f"\n[{sc.id}] {sc.tc} - {sc.name}")
    print(f"   finals={finals}  worst={tl.worst_zone()}  audio={tl.audio_target()}  "
          f"standby={tl.standby()}")
    if verbose:
        for tk in tl.ticks:
            shown = {z: tk["states"][z]["severity"] for z in zones}
            rng = {z: tk["states"][z]["nearest_range_m"] for z in zones}
            print(f"   t={tk['t']:5}ms  {shown}  range={rng}")


def run_all(verbose: bool) -> None:
    for sc in sim.scenarios():
        summarize(sc, verbose)


def live(sc, host: str, port: int, dt_ms: int, loops: int) -> None:
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    client.connect(host, port, 30)
    client.loop_start()
    simu, _ = build(enable_camera=sc.enable_camera)
    n = sc.duration_ms // dt_ms
    print(f"[live] publishing {sc.id} ({sc.name}); Ctrl-C to stop")
    try:
        for _ in range(loops) if loops > 0 else iter(int, 1):
            for tick in range(n + 1):
                now = int(time.time() * 1000)
                if sc.vehicle is not None:
                    client.publish("bsw/vehicle", json.dumps({
                        "schema": "bsw.vehicle/1", "ts": now, "ts_kind": "epoch_ms", **sc.vehicle}))
                dropped = sc.dropped_at(tick * dt_ms)
                for m in simu.readings_at(sc.objects_at(simu, tick * dt_ms), ts=now, tick=tick,
                                          group_fire=sc.group_fire, noise_m=sc.noise_m,
                                          dropout=sc.dropout):
                    if m["sensor_id"] in dropped:
                        continue
                    topic = "bsw/detection/" if m["schema"].startswith("bsw.detection") else "bsw/sensor/"
                    client.publish(topic + m["sensor_id"], json.dumps(m))
                time.sleep(dt_ms / 1000.0)
    except KeyboardInterrupt:
        print("\n[live] stopping")
    finally:
        client.loop_stop()
        client.disconnect()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario", nargs="?", default="all", help="scenario id (S1..S6, F1..) or 'all'")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the tick-by-tick timeline")
    ap.add_argument("--live", action="store_true", help="publish to the broker in real time")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--dt", type=int, default=100, help="ms per tick")
    ap.add_argument("--loops", type=int, default=0, help="live: repeat count (0 = forever)")
    args = ap.parse_args()

    if args.scenario == "all":
        if args.live:
            ap.error("--live needs a single scenario id, e.g. S2")
        run_all(args.verbose)
        return

    table = sim.by_id()
    if args.scenario not in table:
        ap.error(f"unknown scenario {args.scenario!r}; choose from {', '.join(table)} or 'all'")
    sc = table[args.scenario]
    live(sc, args.host, args.port, args.dt, args.loops) if args.live else summarize(sc, args.verbose)


if __name__ == "__main__":
    main()
