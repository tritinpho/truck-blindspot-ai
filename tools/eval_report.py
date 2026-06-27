#!/usr/bin/env python3
"""Regenerate the evaluation-report figures, reproducibly (Nội dung 6, 11 §11.6 / §11.7).

This is the "not anecdotal" generator behind [docs/21-evaluation-report-inputs.md]: one command
recomputes every number the report cites, deterministically, from the real fusion engine over the
scripted scenarios — no broker, no wall-clock, no hardware. Re-running yields byte-identical figures.

It assembles, in one Markdown dump:
  1. Scenario outcomes (S1-S6 + F1/F2/F3) — the per-zone finals / worst-zone / audio the L3 suite asserts.
  2. Indicative danger-path latency (S1-S6) — sim debounce only; +~70 ms physical = est-real (doc 19).
  3. Ultrasonic group-fire per-sensor rate (TC-F5, ADR-0007).
  4. Canonical-run replay metrics — drives all scenarios → logs/events.jsonl → summarize_events
     (the SAME path tools/log_replay.py reproduces), so the metric is auditable, not hand-typed.
  5. Metric vs target (11 §11.3) with an honest status: met-in-sim / regression-only / NEEDS-L4 / NEEDS-L5.
  6. Test-case coverage (TC-S1..S6 + TC-F1..F5).

HONESTY (11 §11.2, 14 §P2 #6): the sim derives detection from zone geometry, so the headline
detection rate, end-to-end latency, and absolute false-positive rate are **L4 bench** numbers, NOT
these. What is proven here is logic + regression; the status column says exactly which is which.

    python tools/eval_report.py                 # print the Markdown report (writes logs/events.jsonl)
    python tools/eval_report.py --out docs/_generated/eval-figures.md
    python tools/eval_report.py --no-log         # skip writing the canonical log (use a temp dir)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from random import Random

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services" / "fusion-engine"))

import sim  # noqa: E402
from fusion.eventlog import EventLog  # noqa: E402
from fusion.service import FusionService  # noqa: E402
from sim.metrics import danger_latency_ms, summarize_events  # noqa: E402

DT_MS = 100
MASTER_HZ = 1000 // DT_MS        # 10 Hz master tick
PHYSICAL_PATH_MS = 70            # sensor+broker×2+HMI path the sim omits (03 §3.5 / doc 19)
GAP_MS = 10_000                  # spacer between scenarios in the canonical log (keeps ts monotonic)


# --------------------------------------------------------------- 1. scenario outcomes (L3)

def _outcome_row(label: str, sc) -> dict:
    tl = sim.run(sc)
    zones = sorted({tr.zone for tr in sc.tracks})
    return {
        "id": label,
        "tc": sc.tc,
        "name": sc.name,
        "finals": {z: tl.final(z) for z in zones},
        "reached_danger": [z for z in zones if tl.reached(z, "DANGER")],
        "worst": tl.worst_zone(),
        "audio": tl.audio_target(),
        "standby": tl.standby(),
    }


def scenario_outcomes() -> list[dict]:
    """S1-S6 + F1/F2 as-defined, plus both F3 camera variants (VRU vs vehicle)."""
    rows: list[dict] = []
    for sc in sim.scenarios():
        if sc.id == "F3":
            for cls in ("pedestrian", "vehicle"):
                v = sim.by_id()["F3"]
                v.tracks[0].cls = cls
                rows.append(_outcome_row(f"F3·{cls}", v))
        else:
            rows.append(_outcome_row(sc.id, sc))
    return rows


# --------------------------------------------------------------- 2. indicative latency (S1-S6)

def latency_rows() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    measured: list[int] = []
    for sc in sim.scenarios():
        if not sc.id.startswith("S"):
            continue
        tl = sim.run(sc, dt_ms=DT_MS)
        for zone in sorted({tr.zone for tr in sc.tracks}):
            ts = [tk["t"] for tk in tl.ticks]
            rng = [tk["states"][zone]["nearest_range_m"] for tk in tl.ticks]
            sev = [tk["states"][zone]["severity"] for tk in tl.ticks]
            lat = danger_latency_ms(ts, rng, sev, tl.cfg.zones[zone].danger_m)
            rows.append({"id": sc.id, "zone": zone, "sim_ms": lat,
                         "est_real_ms": (lat + PHYSICAL_PATH_MS) if lat is not None else None})
            if lat is not None:
                measured.append(lat)
    measured.sort()
    summ = {"n": len(measured)}
    if measured:
        summ |= {"min": measured[0], "p50": measured[len(measured) // 2], "max": measured[-1],
                 "est_real_p50": measured[len(measured) // 2] + PHYSICAL_PATH_MS}
    return rows, summ


# --------------------------------------------------------------- 3. group-fire rate (TC-F5)

def group_fire_rate(ticks: int = 20) -> list[dict]:
    s, _ = sim.build()
    counts: dict[str, int] = {}
    for tick in range(ticks):
        for m in s.readings_at([], ts=tick * DT_MS, tick=tick, group_fire=True):
            counts[m["sensor_id"]] = counts.get(m["sensor_id"], 0) + 1
    rows = []
    for g in s.sensors:
        if g.modality != "ultrasonic":
            continue
        c = counts.get(g.sensor_id, 0)
        rows.append({"sensor_id": g.sensor_id, "zone": g.zone, "fire_group": g.fire_group,
                     "fires": c, "of_ticks": ticks, "hz": round(c / ticks * MASTER_HZ, 1)})
    return sorted(rows, key=lambda r: (r["fire_group"], r["sensor_id"]))


# --------------------------------------------------------------- 4. canonical run → replay metrics

def canonical_run(log_dir: Path) -> list[dict]:
    """Drive EVERY scenario through a logging FusionService into ONE events.jsonl (the same
    reproducible path tools/log_replay.py reads). Clears prior log files first so a re-run is
    byte-identical (not appended). Returns the transition events. Deterministic (fixed seeds,
    controlled clock); ts is offset per scenario so the log stays monotonic across the battery."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    for name in ("events.jsonl", "commands.jsonl", "events.db"):
        (log_dir / name).unlink(missing_ok=True)

    log = EventLog(log_dir)
    try:
        base = 0
        for sc in sim.scenarios():
            sim_obj, cfg = sim.build(enable_camera=sc.enable_camera)
            svc = FusionService(cfg, log=log)
            rng = Random(sc.seed)
            n = sc.duration_ms // DT_MS
            for tick in range(n + 1):
                t = base + tick * DT_MS
                for topic, payload in sim.scenario_tick_messages(sim_obj, sc, tick, DT_MS, ts=t, rng=rng):
                    svc.handle_message(topic, json.dumps(payload).encode(), float(t), t)
                svc.collect_tick(float(t), t)
            base += sc.duration_ms + GAP_MS
    finally:
        # close even if a scenario raises mid-run, else the leaked events.db/.jsonl handles lock the
        # dir on Windows and the --no-log TemporaryDirectory cleanup fails, masking the real error.
        log.close()
    return [json.loads(line) for line in
            (log_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------- 5 + 6. status & coverage maps

def metric_status(replay: dict, gfire: list[dict], lat_summ: dict) -> list[dict]:
    """11 §11.3 metric → target → what the sim shows now → honest status. Computed evidence is
    spliced in where the sim produces it; headline figures are flagged NEEDS-L4."""
    total = replay["total"]
    us_hz = sorted({r["hz"] for r in gfire})
    lat_txt = (f"sim p50 {lat_summ.get('p50','?')} ms → est-real ~{lat_summ.get('est_real_p50','?')} ms"
               if lat_summ.get("n") else "no clean approach crossing")
    return [
        {"metric": "Detection rate", "target": "≥ 95%",
         "evidence": "L3: every S1-S6 object reaches the correct zone severity; but the sim derives "
                     "detection from geometry (measures the model against itself)",
         "status": "regression-only · NEEDS-L4 (headline)"},
        {"metric": "End-to-end latency (danger-path)", "target": "≤ 200 ms (stretch ≤ 150)",
         "evidence": f"indicative {lat_txt} (+~{PHYSICAL_PATH_MS} ms physical path, doc 19); "
                     "single-observer tool exists (latency_observer.py)",
         "status": "met-in-sim (indicative) · NEEDS-L4 (headline)"},
        {"metric": "False-positive rate", "target": "≤ a tuned threshold (low enough to keep on)",
         "evidence": "nuisance sweep characterizes dwell/episodes/flicker; operating point validated "
                     "at the knee (doc 19). Absolute rate needs real clutter/multipath",
         "status": "regression-only · NEEDS-L4 (absolute rate)"},
        {"metric": "Zone-localization accuracy", "target": "≥ 98%",
         "evidence": "L3: every alert lands in the config-mapped zone (FR-02/03); sensor→zone is "
                     "central config, not geometry-derived",
         "status": "met-in-sim · NEEDS-L4 (real cones)"},
        {"metric": "Glance-time to locate", "target": "≤ 1 s in ≥ 95%",
         "evidence": "HMI glanceability designed (06); not measured in sim",
         "status": "NEEDS-L5 (usability review)"},
        {"metric": "Flicker", "target": "≈ 0 (debounce holds)",
         "evidence": f"canonical run: {total['flicker']} flicker event(s) across {total['events']} "
                     "transitions / all scenarios; F2 boundary jitter ≤ 3 transitions; sweep flicker "
                     "0 at the chosen point (doc 19)",
         "status": "met-in-sim"},
        {"metric": "Fault visibility (UNKNOWN, never SAFE)", "target": "100%",
         "evidence": f"TC-F1: RIGHT ages to UNKNOWN after unplug (never stale-green). Of the "
                     f"{total['to_unknown']} to-UNKNOWN transitions, most are the NFR-12 boot "
                     "warming-up (a zone starts UNKNOWN until its first reading, not fake SAFE — see "
                     "per-zone table); the fault-driven one is RIGHT",
         "status": "met-in-sim"},
        {"metric": "Compute liveness (freeze → UNKNOWN)", "target": "100% within freshness window",
         "evidence": "TC-F4: HMI liveness clock + fusion LWT/heartbeat → SIGNAL LOST on kill "
                     "(HMI unit tests + live demo, 17 §5)",
         "status": "met-in-sim (demo) · NEEDS-L4 (bench boot)"},
        {"metric": "Refresh rate", "target": "HMI ≥ 10 Hz; ultrasonic ~5 Hz/sensor",
         "evidence": f"HMI rAF loop ≥ 10 Hz (S3); group-fire gives {us_hz} Hz/sensor in sim "
                     "(~½ master, ADR-0007)",
         "status": "met-in-sim · NEEDS-L4 (real Hz on HW)"},
        {"metric": "Recovery (auto-restart)", "target": "< 5 s",
         "evidence": "compose restart policy + HMI auto-recovers to MONITORING on fusion return",
         "status": "regression-only · NEEDS-L4 (timed on HW)"},
    ]


def tc_coverage() -> list[dict]:
    """Where each 11 §11.4 case is proven (from doc 18 §M3 evidence)."""
    return [
        ("TC-S1", "pull-away FRONT_RIGHT", "L3 test_TC_S1 + shim [S1]", "met-in-sim"),
        ("TC-S2", "right-turn squeeze", "L3 test_TC_S2 + shim + broker job", "met-in-sim"),
        ("TC-S3", "left lane change", "L3 test_TC_S3 + shim [S3]", "met-in-sim"),
        ("TC-S4", "reversing", "L3 test_TC_S4 + shim + broker job", "met-in-sim"),
        ("TC-S5", "dense crawl (worst wins)", "L3 test_TC_S5 + shim [S5]", "met-in-sim"),
        ("TC-S6", "parked standby (audio silent)", "L3 test_TC_S6 + shim [S6]", "met-in-sim"),
        ("TC-F1", "sensor unplugged → UNKNOWN", "L3 test_TC_F1 + shim", "met-in-sim"),
        ("TC-F2", "boundary jitter (debounce holds)", "L3 test_TC_F2 + shim finals", "met-in-sim"),
        ("TC-F3", "VRU vs vehicle (phase-2 cam)", "L3 test_TC_F3 (both) + shim", "regression-only (phase-2)"),
        ("TC-F4", "compute freeze → SIGNAL LOST", "HMI unit tests + live kill demo (17 §5)", "met-in-sim (demo) · NEEDS-L4"),
        ("TC-F5", "group-fire ~½ rate/sensor", "L3 test_TC_F5 + shim counts", "met-in-sim · NEEDS-L4 (real Hz)"),
    ]


# ----------------------------------------------------------------------------- build + render

def build_report(events: list[dict]) -> dict:
    replay = summarize_events(events)
    gfire = group_fire_rate()
    lat_rows, lat_summ = latency_rows()
    return {
        "outcomes": scenario_outcomes(),
        "latency": {"rows": lat_rows, "summary": lat_summ},
        "group_fire": gfire,
        "replay": replay,
        "metric_status": metric_status(replay, gfire, lat_summ),
        "tc_coverage": tc_coverage(),
    }


def _md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def render_markdown(report: dict) -> str:
    L: list[str] = []
    L.append("# Evaluation figures (generated by `tools/eval_report.py`)\n")
    L.append("> Reproducible — re-run to regenerate. Headline detection/latency/abs-false-positive "
             "are **L4 bench**, not these sim figures (11 §11.2). Status column says which is which.\n")

    L.append("\n## 1. Scenario outcomes (L3, S1-S6 + faults)\n")
    L.append(_md_table(
        ["scn", "TC", "finals", "reached DANGER", "worst", "audio", "standby"],
        [[o["id"], o["tc"], json.dumps(o["finals"]), ",".join(o["reached_danger"]) or "—",
          o["worst"] or "—", o["audio"], o["standby"]] for o in report["outcomes"]]))

    L.append("\n\n## 2. Indicative danger-path latency (sim, S1-S6)\n")
    s = report["latency"]["summary"]
    L.append(_md_table(
        ["scn", "zone", "sim ms", "est-real ms (+70)"],
        [[r["id"], r["zone"], r["sim_ms"] if r["sim_ms"] is not None else "n/a",
          r["est_real_ms"] if r["est_real_ms"] is not None else "n/a"]
         for r in report["latency"]["rows"]]))
    if s.get("n"):
        L.append(f"\n\n_n={s['n']} clean approach crossing(s) · min {s['min']} · p50 {s['p50']} · "
                 f"max {s['max']} ms (sim) → est-real p50 ~{s['est_real_p50']} ms; "
                 f"NFR-01 danger-path ≤ 200 ms. Only un-boosted approaches yield a latency "
                 f"(context-boosted S2–S6 warn before the crossing), so n is small by construction "
                 f"— indicative, not a distribution and not headline._")

    L.append("\n\n## 3. Ultrasonic group-fire rate (TC-F5, ADR-0007)\n")
    L.append(_md_table(
        ["sensor_id", "zone", "fire_group", "fires/ticks", "≈ Hz"],
        [[r["sensor_id"], r["zone"], r["fire_group"], f"{r['fires']}/{r['of_ticks']}", r["hz"]]
         for r in report["group_fire"]]))
    L.append("\n\n_Two non-adjacent groups alternate → each sensor ~½ the 10 Hz master ≈ 5 Hz._")

    L.append("\n\n## 4. Canonical-run replay metrics (logs/events.jsonl → summarize_events)\n")
    t = report["replay"]["total"]
    L.append(f"_Across the full scenario battery: **{t['events']}** transitions over **{t['zones']}** "
             f"zones · to-DANGER **{t['to_danger']}** · to-UNKNOWN **{t['to_unknown']}** · "
             f"flicker **{t['flicker']}**._\n")
    L.append("\n" + _md_table(
        ["zone", "transitions", "to-DANGER", "to-UNKNOWN", "flicker"],
        [[z, d["transitions"], d["to_danger"], d["to_unknown"], d["flicker"]]
         for z, d in sorted(report["replay"]["per_zone"].items())]))

    L.append("\n\n## 5. Metric vs target (11 §11.3) — with honest status\n")
    L.append(_md_table(
        ["metric", "target", "evidence now (sim/regression)", "status"],
        [[m["metric"], m["target"], m["evidence"], m["status"]] for m in report["metric_status"]]))

    L.append("\n\n## 6. Test-case coverage (11 §11.4)\n")
    L.append(_md_table(
        ["TC", "scenario", "proven where", "status"],
        [[a, b, c, d] for a, b, c, d in report["tc_coverage"]]))
    L.append("")
    return "\n".join(L)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log-dir", type=Path, default=REPO / "logs",
                    help="where to write the canonical events.jsonl (default: repo logs/)")
    ap.add_argument("--no-log", action="store_true",
                    help="don't write into logs/; use a throwaway temp dir for the canonical run")
    ap.add_argument("--out", type=Path, help="also write the Markdown report to this file")
    args = ap.parse_args()

    if args.no_log:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            events = canonical_run(Path(td))
    else:
        events = canonical_run(args.log_dir)
        print(f"[eval] canonical log → {args.log_dir / 'events.jsonl'} "
              f"({len(events)} transitions)", file=sys.stderr)

    md = render_markdown(build_report(events))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md + "\n", encoding="utf-8")
        print(f"[eval] wrote {args.out}", file=sys.stderr)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
