"""Reproducible logs (11 §11.6) — the report's metrics must be reproducible, not anecdotal.

The fusion engine writes zone-severity transitions to logs/events.jsonl (eventlog.py). This test
proves two things the evaluation relies on:
  1. a run actually WRITES events.jsonl (the fail-loud path leaves an audit trail), and
  2. replaying the SAME scenario produces a BYTE-IDENTICAL log → identical replayed metrics
     (tools/log_replay.py / sim.metrics.summarize_events).

Driven through the real FusionService on a controlled clock (no broker), so it's deterministic in
CI. This is the regression guard behind `tools/log_replay.py`.
"""
from __future__ import annotations

import json
from random import Random

import pytest

import sim
from fusion.eventlog import EventLog
from fusion.service import FusionService
from sim.metrics import summarize_events

DT_MS = 100


def run_logged(sc, log_dir) -> str:
    """Drive a scenario through a logging FusionService; return the events.jsonl contents."""
    sim_obj, cfg = sim.build(enable_camera=sc.enable_camera)
    log = EventLog(log_dir)
    svc = FusionService(cfg, log=log)
    rng = Random(sc.seed)
    n = sc.duration_ms // DT_MS
    for tick in range(n + 1):
        t = tick * DT_MS
        for topic, payload in sim.scenario_tick_messages(sim_obj, sc, tick, DT_MS, ts=t, rng=rng):
            svc.handle_message(topic, json.dumps(payload).encode(), float(t), t)
        svc.collect_tick(float(t), t)
    log.close()
    return (log_dir / "events.jsonl").read_text(encoding="utf-8")


def load(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_run_writes_events_jsonl(tmp_path):
    text = run_logged(sim.by_id()["S2"], tmp_path / "run")
    rows = load(text)
    assert rows, "fusion run produced no transitions in events.jsonl"
    assert any(r["to"] == "DANGER" and r["zone_id"] == "RIGHT" for r in rows)
    # schema of a transition row (what log_replay consumes)
    assert set(rows[0]) == {"ts", "zone_id", "from", "to", "nearest_range_m", "reason"}


@pytest.mark.parametrize("sid", ["S1", "S2", "S4", "S5", "F1"])
def test_event_log_byte_identical_across_runs(tmp_path, sid):
    a = run_logged(sim.by_id()[sid], tmp_path / "a")
    b = run_logged(sim.by_id()[sid], tmp_path / "b")
    assert a == b, f"{sid}: events.jsonl differs between identical runs (not reproducible)"


@pytest.mark.parametrize("sid", ["S1", "S2", "S4", "S5", "F1"])
def test_replayed_metrics_identical(tmp_path, sid):
    a = summarize_events(load(run_logged(sim.by_id()[sid], tmp_path / "a")))
    b = summarize_events(load(run_logged(sim.by_id()[sid], tmp_path / "b")))
    assert a == b, f"{sid}: replayed metrics differ between identical runs"
