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
from random import Random

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs on the Windows cp1252 console

import sim  # noqa: E402
from sim.metrics import danger_latency_ms  # noqa: E402
from sim.runner import build, scenario_tick_messages  # noqa: E402

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


def _danger_latency(tl, zone: str, danger_m: float) -> int | None:
    """Indicative danger-path latency for one zone in a timeline (sim.metrics.danger_latency_ms)."""
    ts = [tk["t"] for tk in tl.ticks]
    rng = [tk["states"][zone]["nearest_range_m"] for tk in tl.ticks]
    sev = [tk["states"][zone]["severity"] for tk in tl.ticks]
    return danger_latency_ms(ts, rng, sev, danger_m)


def latency_summary(dt_ms: int) -> None:
    """Print an INDICATIVE danger-path latency per zone from the deterministic sim, over the
    operational scenarios (S1-S6). Indicative only: the sim derives detection from zone geometry,
    so the headline latency must come from L4 bench (11 §11.2, 14 §P2 #6). Use
    tools/latency_observer.py on a --live run for the real single-observer measurement."""
    print(f"indicative danger-path latency (sim approach-path, dt={dt_ms}ms; headline is L4 bench):")
    print(f"  {'scn':4} {'zone':12} {'latency':>9}  note")
    measured: list[int] = []
    for sc in sim.scenarios():
        if not sc.id.startswith("S"):
            continue  # operational scenarios only; F* are fault/jitter cases, not danger-path
        tl = sim.run(sc, dt_ms=dt_ms)
        for zone in sorted({tr.zone for tr in sc.tracks}):
            lat = _danger_latency(tl, zone, tl.cfg.zones[zone].danger_m)
            if lat is None:
                note = "boosted/standby/static — early or no danger-crossing"
                print(f"  {sc.id:4} {zone:12} {'n/a':>9}  {note}")
            else:
                print(f"  {sc.id:4} {zone:12} {f'{lat} ms':>9}  approach → confirmed DANGER")
                measured.append(lat)
    if measured:
        measured.sort()
        print(f"  --- n={len(measured)}  min={measured[0]}  "
              f"p50={measured[len(measured)//2]}  max={measured[-1]}  ms "
              f"(NFR-01 danger-path target <= 200 ms; indicative, not headline)")
    else:
        print("  --- no clean approach-path crossing in S1-S6 (boosted/static); use --live observer")


def live(sc, host: str, port: int, dt_ms: int, loops: int) -> None:
    import paho.mqtt.client as mqtt
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()
    try:
        client.connect(host, port, 30)
    except OSError as e:
        print(f"[live] broker unreachable at {host}:{port} ({e})", file=sys.stderr)
        return
    client.loop_start()
    simu, _ = build(enable_camera=sc.enable_camera)
    n = sc.duration_ms // dt_ms
    print(f"[live] publishing {sc.id} ({sc.name}); Ctrl-C to stop")
    try:
        for _ in range(loops) if loops > 0 else iter(int, 1):
            # Seed ONCE per loop, not per tick. scenario_tick_messages → readings_at defaults to a
            # fresh Random(0) when rng is None, which would make a noisy scenario emit the SAME draw
            # every tick (a constant DC offset, not jitter) — so the live noisy-boundary demo never
            # exercises debounce. A per-loop Random(sc.seed) gives real jitter, identical each loop.
            rng = Random(sc.seed)
            for tick in range(n + 1):
                now = int(time.time() * 1000)
                # same per-tick wire stream the integration shim asserts on (sim.scenario_tick_messages)
                for topic, payload in scenario_tick_messages(simu, sc, tick, dt_ms, ts=now, rng=rng):
                    client.publish(topic, json.dumps(payload))
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
    ap.add_argument("--latency", action="store_true",
                    help="print indicative danger-path latency across all scenarios (sim, not headline)")
    args = ap.parse_args()

    if args.latency:
        latency_summary(args.dt)
        return

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
