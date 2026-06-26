#!/usr/bin/env python3
"""Threshold / debounce sweep — justify the operating point with data (S6, NFR-09, 11 §11.6).

Sweeps the FR-09 anti-flicker debounce levers (`confirm`, `release_margin_m`, `release`,
`immediate_danger_factor`) and reports the sensitivity ↔ false-alarm trade-off, so the chosen
defaults are backed by numbers, not guesswork:

  * detection (sensitivity): danger-path latency + did-it-reach-DANGER on clean APPROACH scenarios.
  * nuisance (false-alarm proxy): a noisy object hovering just OUTSIDE danger_m should hold CAUTION;
    we count how often it is wrongly pushed to DANGER (rising episodes), how long it dwells there,
    and severity flicker — averaged over many noise seeds.

IMPORTANT (11 §11.2, 14 §P2 #6): the sim derives detection from geometry and injects sensor noise,
so this characterizes the DEBOUNCE response to sensor noise — a defensible *starting* operating
point. The **absolute** false-positive rate (real-world clutter/multipath) is an **L4 bench**
number, not this. Per-zone thresholds are also live-tunable at runtime via `bsw/cmd/set_threshold`.

    python tools/threshold_sweep.py                 # the confirm × margin grid + recommendation
    python tools/threshold_sweep.py --seeds 20      # more noise seeds (steadier nuisance means)
    python tools/threshold_sweep.py --release --idf # also sweep release / immediate_danger_factor
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services" / "fusion-engine"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fusion.engine import load_config  # noqa: E402
from sim import Sim, build, run_on  # noqa: E402
from sim.metrics import danger_dwell_frac, danger_latency_ms, summarize_events  # noqa: E402
from sim.scenarios import Scenario, approach, static  # noqa: E402

ZONES = REPO / "config" / "zones.example.json"
SENSORS = REPO / "config" / "sensors.example.json"

# Defaults from config/zones.example.json — the row we are validating.
DEFAULTS = {"confirm": 2, "release": 4, "release_margin_m": 0.2, "immediate_danger_factor": 0.6}

# The sim measures only the FUSION debounce contribution to latency. The end-to-end NFR-01 budget
# also pays the physical path the sim omits — sensor sample+publish (~30) + broker×2 (~10) + HMI
# render+audio (~30) ≈ 70 ms (03 §3.5). So we judge each config against the requirement using an
# estimated real latency = sim debounce + this, i.e. we must leave ~70 ms of headroom in-sim.
PHYSICAL_PATH_MS = 70

# Detection = clean approaches, no context boost (isolate the debounce), with the real group-fire
# rate. (zone RIGHT: caution_m 1.8, danger_m 1.0.) budget = NFR-01 path target (ms).
DETECTION = [
    ("deep",     Scenario("DET-deep", "deep approach RIGHT", "TC-tune",
                          [approach("RIGHT", 3.0, 0.5, 4000)], None, 4000), 200),   # danger-path
    ("boundary", Scenario("DET-bnd", "boundary approach RIGHT", "TC-tune",
                          [approach("RIGHT", 3.0, 0.9, 4000)], None, 4000), 300),   # boundary-path
]

# Nuisance = a noisy object hovering just OUTSIDE danger_m (mean in the CAUTION band): the correct
# behaviour is to HOLD CAUTION. Continuous sampling (group_fire off) maximally stresses debounce.
NUISANCE = [
    Scenario("NUI-106", "noisy boundary RIGHT @1.06m", "TC-tune",
             [static("RIGHT", 1.06, 3000)], None, 3000, group_fire=False, noise_m=0.12),
    Scenario("NUI-115", "noisy boundary RIGHT @1.15m", "TC-tune",
             [static("RIGHT", 1.15, 3000)], None, 3000, group_fire=False, noise_m=0.15),
]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def make_cfg(**overrides):
    cfg = load_config(ZONES, SENSORS)
    cfg.tun.update(overrides)
    return cfg


def _zone_series(tl, zone):
    return ([tk["t"] for tk in tl.ticks],
            [tk["states"][zone]["nearest_range_m"] for tk in tl.ticks],
            [tk["states"][zone]["severity"] for tk in tl.ticks])


def evaluate(sim: Sim, cfg, seeds: list[int], dt_ms: int = 100) -> dict:
    """Detection + nuisance metrics for one config. Pure read of deterministic timelines."""
    detection = {}
    for name, sc, budget in DETECTION:
        zone = sc.tracks[0].zone
        tl = run_on(sc, sim, cfg, dt_ms=dt_ms)
        ts, rng, sev = _zone_series(tl, zone)
        lat = danger_latency_ms(ts, rng, sev, cfg.zones[zone].danger_m)
        detection[name] = {"reached": "DANGER" in sev, "latency": lat, "budget": budget}

    episodes, dwell, flicker = [], [], []
    for sc in NUISANCE:
        zone = sc.tracks[0].zone
        for s in seeds:
            tl = run_on(sc, sim, cfg, dt_ms=dt_ms, seed=s)
            _, _, sev = _zone_series(tl, zone)
            pz = summarize_events(tl.transition_events())["per_zone"].get(zone, {})
            episodes.append(pz.get("to_danger", 0))
            flicker.append(pz.get("flicker", 0))
            dwell.append(danger_dwell_frac(sev))
    return {
        "detection": detection,
        "nui_episodes": _mean(episodes),
        "nui_dwell": _mean(dwell),
        "nui_flicker": _mean(flicker),
    }


def meets_budget(m: dict) -> bool:
    """Met iff every approach reaches DANGER and its ESTIMATED REAL latency (sim debounce +
    physical path) is within the NFR-01 budget — so the operating point holds on real hardware,
    not just in the sim that omits the sensor/broker/render path."""
    return all(d["reached"] and d["latency"] is not None
               and d["latency"] + PHYSICAL_PATH_MS <= d["budget"]
               for d in m["detection"].values())


def _fmt_lat(m: dict) -> str:
    return "/".join((str(d["latency"]) if d["latency"] is not None else "MISS")
                    for d in m["detection"].values())


def _fmt_real(m: dict) -> str:
    return "/".join((str(d["latency"] + PHYSICAL_PATH_MS) if d["latency"] is not None else "MISS")
                    for d in m["detection"].values())


def sweep(sim, seeds, confirms, margins) -> list[dict]:
    rows = []
    for confirm in confirms:
        for margin in margins:
            cfg = make_cfg(confirm=confirm, release=DEFAULTS["release"], release_margin_m=margin,
                           immediate_danger_factor=DEFAULTS["immediate_danger_factor"])
            m = evaluate(sim, cfg, seeds)
            rows.append({"confirm": confirm, "margin": margin, **m})
    return rows


def print_grid(rows, title, seeds):
    print(f"\n{title}  (nuisance averaged over {len(seeds)} seeds; lat = deep/boundary)")
    print(f"  {'confirm':>7} {'margin':>6} {'ok':>3} {'sim(ms)':>8} {'est-real':>9} "
          f"{'nui_DANGER/run':>14} {'dwell%':>7} {'flicker':>7}  note")
    for r in rows:
        is_def = r["confirm"] == DEFAULTS["confirm"] and abs(r["margin"] - DEFAULTS["release_margin_m"]) < 1e-9
        ok = meets_budget(r)
        note = ("← current default" if is_def else "") + ("" if ok else "  ✗ est-real over budget")
        print(f"  {r['confirm']:>7} {r['margin']:>6.2f} {'yes' if ok else 'no':>3} {_fmt_lat(r):>8} "
              f"{_fmt_real(r):>9} {r['nui_episodes']:>14.2f} {100*r['nui_dwell']:>6.1f}% "
              f"{r['nui_flicker']:>7.2f}  {note}")
    print(f"  (est-real = sim debounce + {PHYSICAL_PATH_MS} ms physical path; budgets deep 200 / "
          f"boundary 250, NFR-01)")


def recommend(rows):
    ok = [r for r in rows if meets_budget(r)]
    if not ok:
        print("\nNo config met the detection budgets — widen the grid.")
        return
    # meet detection, then minimise false alarms (episodes → dwell → flicker), then prefer faster
    # meet detection (with real-path headroom), then no flicker (FR-09's named target), then
    # fewest false-DANGER episodes, then least dwell, then faster.
    ok.sort(key=lambda r: (r["nui_flicker"], r["nui_episodes"], r["nui_dwell"],
                           max(d["latency"] for d in r["detection"].values())))
    best = ok[0]
    print(f"\nRecommended operating point: confirm={best['confirm']}, "
          f"release_margin_m={best['margin']:.2f}, release={DEFAULTS['release']}, "
          f"immediate_danger_factor={DEFAULTS['immediate_danger_factor']}")
    print(f"  latency sim/est-real (deep/boundary) = {_fmt_lat(best)} / {_fmt_real(best)} ms "
          f"(budgets 200/250); nuisance DANGER episodes/run = {best['nui_episodes']:.2f}, "
          f"dwell {100*best['nui_dwell']:.1f}%, flicker {best['nui_flicker']:.2f}")
    print("  NB: absolute false-positive rate is an L4-bench number; this is the sim debounce response.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=12, help="noise seeds per nuisance scenario")
    ap.add_argument("--release", action="store_true", help="also sweep release at the default confirm/margin")
    ap.add_argument("--idf", action="store_true", help="also sweep immediate_danger_factor")
    args = ap.parse_args()

    sim, _ = build(ZONES, SENSORS)
    seeds = list(range(1, args.seeds + 1))

    rows = sweep(sim, seeds, confirms=[1, 2, 3], margins=[0.1, 0.2, 0.3])
    print_grid(rows, "confirm × release_margin_m  (release=4, immediate_danger_factor=0.6)", seeds)
    recommend(rows)

    if args.release:
        rrows = []
        for release in [2, 3, 4, 6]:
            cfg = make_cfg(confirm=DEFAULTS["confirm"], release=release,
                           release_margin_m=DEFAULTS["release_margin_m"],
                           immediate_danger_factor=DEFAULTS["immediate_danger_factor"])
            rrows.append({"confirm": DEFAULTS["confirm"], "margin": DEFAULTS["release_margin_m"],
                          "release": release, **evaluate(sim, cfg, seeds)})
        print("\nrelease sweep (confirm=2, margin=0.2):")
        for r in rrows:
            print(f"  release={r['release']}: lat {_fmt_lat(r)} ms, nuisance dwell "
                  f"{100*r['nui_dwell']:.1f}%, flicker {r['nui_flicker']:.2f}, episodes {r['nui_episodes']:.2f}")

    if args.idf:
        print("\nimmediate_danger_factor sweep (confirm=2, release=4, margin=0.2):")
        for idf in [0.4, 0.5, 0.6, 0.7]:
            cfg = make_cfg(confirm=DEFAULTS["confirm"], release=DEFAULTS["release"],
                           release_margin_m=DEFAULTS["release_margin_m"], immediate_danger_factor=idf)
            m = evaluate(sim, cfg, seeds)
            print(f"  idf={idf}: lat {_fmt_lat(m)} ms, nuisance episodes {m['nui_episodes']:.2f}, "
                  f"dwell {100*m['nui_dwell']:.1f}%")


if __name__ == "__main__":
    main()
