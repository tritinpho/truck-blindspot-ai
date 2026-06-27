"""L3 scenario (sim) tests — 11 §11.2 level L3.

Replays the scripted scenarios S1-S6 (and fault cases F1-F3, F5) deterministically through the
REAL fusion engine via the geometric simulator, and asserts the per-zone severity timeline +
the HMI-side priority/audio policy. No broker, no wall-clock — fully reproducible (the runner
drives a controlled clock). Path bootstrap is in the repo-root conftest.py.

These validate logic + guard against regression. Headline detection/latency come from L4 bench,
not from this sim, which derives detection from zone geometry (11 §11.2, 14 §P2 #6).

Run:  pytest -q tests/test_scenarios.py
"""
from __future__ import annotations

import pytest

import sim
from sim import by_id, run
from sim.metrics import summarize_events


# -------------------------------------------------------------- S1-S6 operational scenarios

def test_TC_S1_pullaway_front_right_danger():
    tl = run(by_id()["S1"])
    assert tl.reached("FRONT_RIGHT", "DANGER")
    assert tl.final("FRONT_RIGHT") == "DANGER"
    assert tl.worst_zone() == "FRONT_RIGHT"
    assert tl.audio_target() == "DANGER"          # fast beep


def test_TC_S2_right_turn_squeeze_banner_right():
    tl = run(by_id()["S2"])                         # signal=right boosts the right side
    assert tl.reached("RIGHT", "DANGER")
    assert tl.worst_zone() == "RIGHT"              # primary-alert banner = RIGHT
    assert tl.audio_target() == "DANGER"


def test_TC_S3_left_lane_change_escalates():
    tl = run(by_id()["S3"])                         # signal=left boosts the left side
    assert tl.reached("LEFT", "CAUTION")           # passes through caution as it closes
    assert tl.reached("LEFT", "DANGER")
    assert tl.worst_zone() in {"LEFT", "REAR_LEFT"}


def test_TC_S4_reversing_rear_danger():
    tl = run(by_id()["S4"])                         # gear=reverse boosts the rear
    assert tl.reached("REAR", "DANGER")
    assert tl.final("REAR") == "DANGER"
    assert tl.audio_target() == "DANGER"           # continuous tone


def test_TC_S5_dense_crawl_all_shown_worst_wins():
    tl = run(by_id()["S5"])
    assert tl.final("RIGHT") == "DANGER"
    assert tl.final("LEFT") == "CAUTION"
    assert tl.final("REAR") == "CAUTION"           # all three shown simultaneously
    assert tl.worst_zone() == "RIGHT"              # highest risk_weight × severity
    assert tl.audio_target() == "DANGER"           # single worst, no overload


def test_TC_S6_parked_standby_visual_only():
    tl = run(by_id()["S6"])
    assert tl.standby() is True
    assert tl.final("LEFT") in {"CAUTION", "DANGER"}  # zone stays visible
    assert tl.audio_target() == "SILENT"              # standby suppresses audio nagging


# ---------------------------------------------------------------------- fault / edge cases

def test_TC_F1_sensor_unplugged_goes_unknown():
    tl = run(by_id()["F1"])
    assert tl.reached("RIGHT", "DANGER")           # detected first
    assert tl.final("RIGHT") == "UNKNOWN"          # then unplugged → fail-loud, never stale-green


def test_TC_F2_boundary_jitter_debounce_holds():
    tl = run(by_id()["F2"])
    # naive thresholding at danger_m ± noise would chatter; debounce keeps it flat. The real
    # anti-chatter property is ZERO flicker (no A→B→A reversals); RIGHT makes exactly one ascending
    # CAUTION→DANGER step and holds. The old `<= 3` bound would have passed through a partial
    # debounce regression — assert the actual shape instead.
    assert summarize_events(tl.transition_events())["total"]["flicker"] == 0
    assert tl.transitions("RIGHT") <= 1
    assert tl.final("RIGHT") == "DANGER"


@pytest.mark.parametrize("cls,expected", [("pedestrian", "DANGER"), ("vehicle", "CAUTION")])
def test_TC_F3_vru_escalates_sooner_than_vehicle(cls, expected):
    """Phase-2 (camera): at the same range a VRU's wider threshold escalates sooner than a vehicle's."""
    sc = by_id()["F3"]
    sc.tracks[0].cls = cls
    tl = run(sc)
    assert tl.final("RIGHT") == expected
    if cls == "pedestrian":
        assert tl.reached("RIGHT", "DANGER")
    else:
        assert not tl.reached("RIGHT", "DANGER")   # vehicle stays CAUTION at this range


def test_TC_F5_group_fire_halves_per_sensor_rate():
    """ADR-0007: 8 sensors in 2 non-adjacent groups fire alternately → ~master/2 per sensor."""
    s, _ = sim.build()
    n = 20
    counts: dict[str, int] = {}
    for tick in range(n):
        for m in s.readings_at([], ts=tick * 100, tick=tick, group_fire=True):
            counts[m["sensor_id"]] = counts.get(m["sensor_id"], 0) + 1
    ultrasonic = [g.sensor_id for g in s.sensors if g.modality == "ultrasonic"]
    assert len(ultrasonic) == 8
    for sid in ultrasonic:
        assert 0.4 * n <= counts[sid] <= 0.6 * n   # ~half the master rate, no sensor starved


# ----------------------------------------------------------------------------- smoke / meta

def test_all_scenarios_run_without_error():
    for sc in sim.scenarios():
        tl = run(sc)
        assert len(tl.ticks) > 0
        assert sc.tc.startswith("TC-")
