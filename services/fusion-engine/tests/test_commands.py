"""L2 tests for the live command loop (bsw/cmd — 04 §4.3.6, 05 §5.8).

Two layers, both broker-free:
  * FusionEngine.apply_cmd — pure config mutation (set_threshold / enable_zone / disable_zone).
  * FusionService.handle_message — routes a bsw/cmd wire message (and vehicle / sensor) through
    the SAME path the live service runs, incl. reload_config from disk.

These close the gap where the S3 HMI settings view published bsw/cmd/fusion and fusion ignored it.
"""
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fusion.engine import CAUTION, SAFE, FusionEngine, load_config  # noqa: E402
from fusion.service import FusionService  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
ZONES = REPO / "config/zones.example.json"
SENSORS = REPO / "config/sensors.example.json"


def make_engine() -> FusionEngine:
    return FusionEngine(load_config(ZONES, SENSORS))


def reading(rng, sid="right_mid"):
    return {"sensor_id": sid, "present": True, "range_m": rng, "health": "ok"}


def cmd_bytes(op, args=None):
    return json.dumps({"schema": "bsw.cmd/1", "ts": 0, "op": op, "args": args or {}}).encode()


# ----------------------------------------------------------------- engine.apply_cmd (pure)

def test_set_threshold_mutates_both_bands():
    eng = make_engine()
    changed, _ = eng.apply_cmd("set_threshold", {"zone_id": "RIGHT", "danger_m": 0.6, "caution_m": 1.2})
    assert changed
    assert eng.cfg.zones["RIGHT"].danger_m == 0.6
    assert eng.cfg.zones["RIGHT"].caution_m == 1.2


def test_set_threshold_partial_leaves_other_band():
    eng = make_engine()
    caution0 = eng.cfg.zones["RIGHT"].caution_m
    changed, _ = eng.apply_cmd("set_threshold", {"zone_id": "RIGHT", "danger_m": 0.5})
    assert changed
    assert eng.cfg.zones["RIGHT"].danger_m == 0.5
    assert eng.cfg.zones["RIGHT"].caution_m == caution0  # untouched


def test_set_threshold_unknown_zone_rejected():
    changed, detail = make_engine().apply_cmd("set_threshold", {"zone_id": "NOPE", "danger_m": 0.5})
    assert not changed and "unknown zone" in detail


def test_set_threshold_bad_values_rejected():
    eng = make_engine()
    assert not eng.apply_cmd("set_threshold", {"zone_id": "RIGHT", "danger_m": -1})[0]
    assert not eng.apply_cmd("set_threshold", {"zone_id": "RIGHT", "danger_m": "abc"})[0]
    assert eng.cfg.zones["RIGHT"].danger_m == 1.0  # unchanged from default


def test_disable_zone_drops_it_from_tick_then_enable_restores():
    eng = make_engine()
    assert "LEFT" in eng.cfg.zone_ids
    eng.apply_cmd("disable_zone", {"zone_id": "LEFT"})
    assert "LEFT" not in eng.cfg.zone_ids
    assert "LEFT" not in {s["zone_id"] for s in eng.tick(0.0, 0, None)}
    eng.apply_cmd("enable_zone", {"zone_id": "LEFT"})
    assert "LEFT" in {s["zone_id"] for s in eng.tick(0.0, 0, None)}


def test_hmi_local_ops_are_ignored_by_fusion():
    eng = make_engine()
    for op in ("set_volume", "mute"):
        changed, detail = eng.apply_cmd(op, {})
        assert not changed and "HMI-local" in detail


def test_unknown_op_rejected():
    changed, detail = make_engine().apply_cmd("frobnicate", {})
    assert not changed and "unknown op" in detail


def test_set_threshold_changes_severity_behaviour():
    """Tightening danger_m turns a former-DANGER range into CAUTION (the S6 tuning lever)."""
    eng = make_engine()
    eng.ingest(reading(3.0), 0.0)
    eng.tick(0.0, 0, None)                                  # warm RIGHT to SAFE
    eng.apply_cmd("set_threshold", {"zone_id": "RIGHT", "danger_m": 0.5})  # was 1.0
    st = None
    for t in range(1, 6):                                   # 0.9 m: DANGER before, CAUTION now
        eng.ingest(reading(0.9), t * 100.0)
        st = {s["zone_id"]: s for s in eng.tick(t * 100.0, t * 100, None)}["RIGHT"]
    assert st["severity"] == CAUTION


# ----------------------------------------------------- FusionService routing (the live wiring)

def test_service_routes_cmd_to_engine():
    svc = FusionService(load_config(ZONES, SENSORS))
    res = svc.handle_message("bsw/cmd/fusion", cmd_bytes("set_threshold",
                             {"zone_id": "RIGHT", "danger_m": 0.7}), 0.0, 0)
    assert res is not None
    op, applied, _ = res
    assert op == "set_threshold" and applied
    assert svc.engine.cfg.zones["RIGHT"].danger_m == 0.7


def test_service_routes_vehicle_and_readings():
    svc = FusionService(load_config(ZONES, SENSORS))
    assert svc.handle_message("bsw/vehicle",
                              json.dumps({"schema": "bsw.vehicle/1", "ts": 0, "gear": "reverse"}).encode(),
                              0.0) is None
    assert svc.vehicle["gear"] == "reverse"
    svc.handle_message("bsw/sensor/right_mid", json.dumps(reading(0.5)).encode(), 0.0)
    assert "right_mid" in svc.engine.readings


def test_service_malformed_payload_dropped():
    svc = FusionService(load_config(ZONES, SENSORS))
    assert svc.handle_message("bsw/sensor/right_mid", b"{not json", 0.0) is None
    assert svc.handle_message("bsw/sensor/right_mid", b'"a string, not an object"', 0.0) is None


def test_service_reload_config_from_disk(tmp_path):
    z, s = tmp_path / "zones.json", tmp_path / "sensors.json"
    shutil.copy(ZONES, z)
    shutil.copy(SENSORS, s)
    svc = FusionService(load_config(z, s), zones_path=z, sensors_path=s)
    assert svc.engine.cfg.zones["RIGHT"].danger_m == 1.0
    data = json.loads(z.read_text(encoding="utf-8"))
    for zone in data["zones"]:
        if zone["id"] == "RIGHT":
            zone["danger_m"] = 0.55
    z.write_text(json.dumps(data), encoding="utf-8")
    op, applied, _ = svc.handle_message("bsw/cmd/fusion", cmd_bytes("reload_config"), 0.0, 0)
    assert op == "reload_config" and applied
    assert svc.engine.cfg.zones["RIGHT"].danger_m == 0.55


def test_service_reload_preserves_zone_runtime(tmp_path):
    """A reload must not flap a zone back to UNKNOWN (replace_config keeps surviving runtime)."""
    z, s = tmp_path / "zones.json", tmp_path / "sensors.json"
    shutil.copy(ZONES, z)
    shutil.copy(SENSORS, s)
    svc = FusionService(load_config(z, s), zones_path=z, sensors_path=s)
    svc.handle_message("bsw/sensor/right_mid", json.dumps(reading(3.0)).encode(), 0.0)
    svc.collect_tick(0.0, 0)
    assert svc.engine.rt["RIGHT"].severity == SAFE
    svc.handle_message("bsw/cmd/fusion", cmd_bytes("reload_config"), 0.0, 0)
    assert svc.engine.rt["RIGHT"].severity == SAFE  # preserved, not reset to UNKNOWN
