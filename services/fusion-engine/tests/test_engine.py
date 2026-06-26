"""L2 (early) unit tests for the fusion engine MVP severity logic.

Pure-Python, no broker. The full L2 suite (debounce, confirm-by-range, context, staleness)
grows here in S2.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fusion.engine import (  # noqa: E402
    CAUTION, DANGER, SAFE, UNKNOWN, ZoneCfg, load_config, zone_severity,
)

RIGHT = ZoneCfg("RIGHT", enabled=True, caution_m=1.8, danger_m=1.0)


def r(range_m, present=True, health="ok"):
    return {"present": present, "range_m": range_m, "health": health}


def test_danger_inside_danger_m():
    assert zone_severity(RIGHT, [r(0.8)]) == (DANGER, 0.8)


def test_caution_band():
    assert zone_severity(RIGHT, [r(1.5)])[0] == CAUTION


def test_safe_beyond_caution():
    assert zone_severity(RIGHT, [r(2.5)])[0] == SAFE


def test_empty_present_is_safe():
    # R2-6: healthy sensors but nothing detected => SAFE, not an undefined min().
    assert zone_severity(RIGHT, [r(None, present=False)]) == (SAFE, None)


def test_no_healthy_is_unknown():
    assert zone_severity(RIGHT, [r(0.8, health="fault")]) == (UNKNOWN, None)


def test_min_over_multiple_sensors():
    assert zone_severity(RIGHT, [r(2.0), r(0.7)]) == (DANGER, 0.7)


def test_load_config_builds_reverse_index():
    repo = pathlib.Path(__file__).resolve().parents[3]
    cfg = load_config(repo / "config/zones.example.json", repo / "config/sensors.example.json")
    assert cfg.sensor_to_zone["right_mid"] == "RIGHT"
    assert "right_mid" in cfg.zone_to_sensors["RIGHT"]
    assert "cam_right" not in cfg.sensor_to_zone  # phase-2 camera is enabled:false
