"""L2 unit tests for the fusion engine.

Pure-Python, no broker. Two layers: the instantaneous `zone_severity` (S1) and the stateful
`FusionEngine` (S2 — debounce, confirm-by-range, hysteresis, local-arrival staleness, context).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fusion.engine import (  # noqa: E402
    CAUTION, DANGER, SAFE, UNKNOWN, Config, FusionEngine, ZoneCfg,
    load_config, zone_severity,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
RIGHT = ZoneCfg("RIGHT", enabled=True, caution_m=1.8, danger_m=1.0)


def r(range_m, present=True, health="ok", sensor="right_mid"):
    return {"sensor_id": sensor, "present": present, "range_m": range_m, "health": health}


# ----------------------------------------------------------------- S1: zone_severity

def test_danger_inside_danger_m():
    assert zone_severity(RIGHT, [r(0.8)]) == (DANGER, 0.8)


def test_caution_band():
    assert zone_severity(RIGHT, [r(1.5)])[0] == CAUTION


def test_safe_beyond_caution():
    assert zone_severity(RIGHT, [r(2.5)])[0] == SAFE


def test_empty_present_is_safe():
    assert zone_severity(RIGHT, [r(None, present=False)]) == (SAFE, None)  # R2-6


def test_no_healthy_is_unknown():
    assert zone_severity(RIGHT, [r(0.8, health="fault")]) == (UNKNOWN, None)


def test_min_over_multiple_sensors():
    assert zone_severity(RIGHT, [r(2.0), r(0.7)]) == (DANGER, 0.7)


def test_load_config_builds_reverse_index():
    cfg = load_config(REPO / "config/zones.example.json", REPO / "config/sensors.example.json")
    assert cfg.sensor_to_zone["right_mid"] == "RIGHT"
    assert "right_mid" in cfg.zone_to_sensors["RIGHT"]
    assert "cam_right" not in cfg.sensor_to_zone  # phase-2 camera is enabled:false


# ----------------------------------------------------------------- S2: FusionEngine

def make_engine() -> FusionEngine:
    cfg = load_config(REPO / "config/zones.example.json", REPO / "config/sensors.example.json")
    return FusionEngine(cfg)


def drive(eng, ranges, vehicle=None, sensor="right_mid", dt=100.0):
    """Ingest one reading per tick (None = no reading) and return RIGHT severity per tick."""
    out, t = [], 0.0
    for rng in ranges:
        if rng is not None:
            eng.ingest(r(rng, sensor=sensor), t)
        states = {s["zone_id"]: s for s in eng.tick(t, int(t), vehicle)}
        out.append(states["RIGHT"]["severity"])
        t += dt
    return out


def warm(eng):
    """Bring RIGHT out of the initial UNKNOWN into steady SAFE (object far)."""
    drive(eng, [3.0])


def test_first_reading_recovers_from_unknown():
    eng = make_engine()
    assert eng.rt["RIGHT"].severity == UNKNOWN  # no data yet
    assert drive(eng, [3.0]) == [SAFE]           # adopts first healthy reading immediately


def test_boundary_escalation_needs_confirm_ticks():
    eng = make_engine(); warm(eng)
    # 0.9 m is DANGER but not "deep" (0.9 > 0.6*1.0) -> needs confirm=2 ticks.
    assert drive(eng, [0.9, 0.9, 0.9]) == [SAFE, DANGER, DANGER]


def test_deep_danger_escalates_immediately():
    eng = make_engine(); warm(eng)
    # 0.5 m <= immediate_danger_factor(0.6) * danger(1.0) -> confirm=1, one tick.
    assert drive(eng, [0.5]) == [DANGER]


def test_caution_escalation():
    eng = make_engine(); warm(eng)
    assert drive(eng, [1.5, 1.5]) == [SAFE, CAUTION]


def test_hysteresis_holds_within_margin():
    eng = make_engine(); warm(eng)
    drive(eng, [0.5])  # -> DANGER
    # 1.1 m: out of danger (1.0) but within release margin (1.0+0.2=1.2) -> hold DANGER.
    assert drive(eng, [1.1, 1.1, 1.1, 1.1, 1.1]) == [DANGER] * 5


def test_release_steps_down_after_clearing_margin():
    eng = make_engine(); warm(eng)
    drive(eng, [0.5])  # DANGER
    # 1.3 m > danger+margin -> clears; release=4 -> 4th tick steps DANGER->CAUTION.
    assert drive(eng, [1.3, 1.3, 1.3, 1.3]) == [DANGER, DANGER, DANGER, CAUTION]


def test_stale_to_unknown_and_recover():
    eng = make_engine()
    eng.ingest(r(2.5), 0.0)
    eng.tick(0.0, 0, None)
    assert eng.rt["RIGHT"].severity == SAFE
    # no fresh reading; age passes stale_after_ms(700): 1st miss holds, 2nd (stale_confirm) -> UNKNOWN
    s1 = {s["zone_id"]: s for s in eng.tick(800.0, 800, None)}["RIGHT"]
    assert s1["severity"] == SAFE and s1["stale"] is False
    s2 = {s["zone_id"]: s for s in eng.tick(900.0, 900, None)}["RIGHT"]
    assert s2["severity"] == UNKNOWN and s2["stale"] is True
    eng.ingest(r(2.5), 1000.0)
    s3 = {s["zone_id"]: s for s in eng.tick(1000.0, 1000, None)}["RIGHT"]
    assert s3["severity"] == SAFE  # recovers immediately on fresh healthy reading


def test_turn_signal_boost_widens_threshold_R2_1():
    eng = make_engine()
    zone = eng.cfg.zones["RIGHT"]
    c0, d0 = eng._effective_thresholds(zone, None, None)
    c1, d1 = eng._effective_thresholds(zone, {"turn_signal": "right"}, None)
    assert d1 > d0 and c1 > c0  # factor>1 WIDENS -> warns sooner
    c2, d2 = eng._effective_thresholds(zone, {"turn_signal": "left"}, None)
    assert (c2, d2) == (c0, d0)  # left signal does not boost a right zone


def test_turn_signal_escalates_sooner_behaviorally():
    # 1.2 m: CAUTION normally, but DANGER when turn=right widens danger 1.0 -> 1.3.
    assert drive(make_engine(), [1.2, 1.2])[-1] == CAUTION
    assert drive(make_engine(), [1.2, 1.2], vehicle={"turn_signal": "right"})[-1] == DANGER


def test_reverse_boosts_rear_zone():
    eng = make_engine()
    rear = eng.cfg.zones["REAR"]
    c0, d0 = eng._effective_thresholds(rear, None, None)
    c1, d1 = eng._effective_thresholds(rear, {"gear": "reverse"}, None)
    assert d1 > d0  # REAR is in reverse_boost_zones


def test_tick_returns_all_enabled_zones():
    eng = make_engine()
    states = eng.tick(0.0, 0, None)
    assert len(states) == len(eng.cfg.zone_ids) == 8
    # untouched zones report UNKNOWN (no sensor reading yet), never a fake SAFE
    assert all(s["severity"] == UNKNOWN for s in states)


def test_standby_flag_when_parked_stationary():
    eng = make_engine()
    eng.ingest(r(2.5), 0.0)
    st = {s["zone_id"]: s for s in eng.tick(0.0, 0, {"gear": "park", "speed_kph": 0})}["RIGHT"]
    assert st["standby"] is True
