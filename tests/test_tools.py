"""Unit tests for the eval-tool cores (sim/metrics.py) — pure, no broker (so they run in CI).
Covers tools/log_replay.py (summarize_events) and tools/latency_observer.py (LatencyPairer)."""
from __future__ import annotations

from sim.metrics import LatencyPairer, summarize_events


def test_summarize_counts_and_flicker():
    events = [
        {"ts": 0, "zone_id": "RIGHT", "from": "SAFE", "to": "CAUTION"},
        {"ts": 100, "zone_id": "RIGHT", "from": "CAUTION", "to": "DANGER"},
        {"ts": 300, "zone_id": "RIGHT", "from": "DANGER", "to": "CAUTION"},  # reversal within 1 s → flicker
        {"ts": 5000, "zone_id": "RIGHT", "from": "CAUTION", "to": "SAFE"},    # 4.7 s later → not flicker
        {"ts": 200, "zone_id": "LEFT", "from": "SAFE", "to": "UNKNOWN"},
    ]
    s = summarize_events(events)
    assert s["total"] == {"events": 5, "zones": 2, "to_danger": 1, "to_unknown": 1, "flicker": 1}
    assert s["per_zone"]["RIGHT"]["transitions"] == 4
    assert s["per_zone"]["RIGHT"]["flicker"] == 1
    assert s["per_zone"]["LEFT"]["to_unknown"] == 1


def test_latency_pairs_stimulus_to_danger():
    p = LatencyPairer()
    p.stimulus("RIGHT", 100.0)
    p.stimulus("RIGHT", 150.0)            # already armed → keep the earliest
    p.effect("RIGHT", "CAUTION", 180.0)   # transient on the way up → must NOT disarm
    p.effect("RIGHT", "DANGER", 250.0)    # fire: 250 - 100 = 150 ms
    assert p.values_ms() == [150.0]


def test_latency_rearms_after_clearing():
    p = LatencyPairer()
    p.stimulus("RIGHT", 100.0)
    p.effect("RIGHT", "DANGER", 250.0)    # 150 ms
    p.effect("RIGHT", "SAFE", 500.0)      # object gone → clear
    p.stimulus("RIGHT", 600.0)
    p.effect("RIGHT", "DANGER", 720.0)    # fresh approach: 120 ms
    s = p.summary()
    assert p.values_ms() == [150.0, 120.0]
    assert s == {"n": 2, "min": 120.0, "max": 150.0, "mean": 135.0, "p50": 150.0}


def test_latency_ignores_danger_without_stimulus():
    p = LatencyPairer()
    p.effect("RIGHT", "DANGER", 100.0)    # no prior stimulus → nothing to pair
    assert p.values_ms() == []
