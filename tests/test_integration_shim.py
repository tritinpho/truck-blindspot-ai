"""Integration shim (L3, broker-free) — prove the LIVE path matches the in-process L3 outcomes.

The S4 L3 suite (test_scenarios.py) drives the engine in-process. This file proves the *wired*
path — publisher → bus → fusion routing → retained bsw/zone/# → subscriber — produces the SAME
result, by running the real FusionService and the real scenario wire stream
(sim.scenario_tick_messages) over an in-process loopback bus (_loopback.py) on a controlled clock.

No broker, fully deterministic → runs in CI on every push. The broker-backed equivalent over real
paho+TCP is test_integration_broker.py (skips when no broker is up). Together they satisfy
build-plan S5 #1: "prove the live path … matches those outcomes for TC-S1..S6 + F1/F2/F3/F5".
"""
from __future__ import annotations

import json
from random import Random

import pytest

import sim
from _loopback import LoopbackBroker
from fusion.service import SUB_TOPICS, FusionService

DT_MS = 100


def drive_over_bus(sc, dt_ms: int = DT_MS):
    """Run a scenario through FusionService over the loopback bus exactly like the live pipeline.
    Returns (finals, zone_timeline, sensor_counts):
      finals         — {zone_id: last severity} as seen by a bsw/zone/# subscriber (the HMI's view)
      zone_timeline  — {zone_id: [severity per tick]} from the subscriber
      sensor_counts  — {sensor_id: #bsw/sensor messages published} (for the group-fire check)."""
    sim_obj, cfg = sim.build(enable_camera=sc.enable_camera)
    svc = FusionService(cfg)
    broker = LoopbackBroker()
    clock = {"ms": 0}

    fusion_c = broker.client()
    fusion_c.on_message = lambda c, u, m: svc.handle_message(
        m.topic, m.payload, float(clock["ms"]), clock["ms"])
    fusion_c.subscribe(SUB_TOPICS)

    seen: dict[str, dict] = {}     # zone_id -> latest wire payload (what a bsw/zone/# consumer holds)
    sink = broker.client()
    sink.on_message = lambda c, u, m: seen.__setitem__(
        m.topic.split("/")[-1], json.loads(m.payload))
    sink.subscribe([("bsw/zone/#", 0)])

    pub = broker.client()
    rng = Random(sc.seed)
    sensor_counts: dict[str, int] = {}
    timeline: dict[str, list[str]] = {}
    n = sc.duration_ms // dt_ms
    for tick in range(n + 1):
        clock["ms"] = tick * dt_ms
        for topic, payload in sim.scenario_tick_messages(sim_obj, sc, tick, dt_ms,
                                                         ts=clock["ms"], rng=rng):
            if topic.startswith("bsw/sensor/"):
                sensor_counts[topic.rsplit("/", 1)[-1]] = sensor_counts.get(topic.rsplit("/", 1)[-1], 0) + 1
            pub.publish(topic, json.dumps(payload).encode())     # → fusion ingests
        states, _ = svc.collect_tick(float(clock["ms"]), clock["ms"])
        for st in states:
            fusion_c.publish(f"bsw/zone/{st['zone_id']}", json.dumps(st).encode(), retain=True)
        for zid, payload in seen.items():
            timeline.setdefault(zid, []).append(payload["severity"])
    finals = {zid: payload["severity"] for zid, payload in seen.items()}
    return finals, timeline, sensor_counts


# ---------------------------------------------------------- live path == in-process L3 outcomes

@pytest.mark.parametrize("sid", list(sim.by_id()))
def test_live_path_matches_inprocess_l3(sid):
    """For every scenario, the finals a bsw/zone/# subscriber sees over the wired path equal the
    finals the in-process L3 runner computes — same engine, same wire stream, now through the
    transport routing + retained publish."""
    sc = sim.by_id()[sid]
    finals, _, _ = drive_over_bus(sc)
    expected = sim.run(sc)
    for zid in finals:
        assert finals[zid] == expected.final(zid), (
            f"{sid}: live {zid}={finals[zid]} != in-process {expected.final(zid)}")
    # the scenario's own touched zones must be present in the wired output
    for zone in {tr.zone for tr in sc.tracks}:
        assert zone in finals, f"{sid}: zone {zone} never published on bsw/zone/#"


def test_live_S2_right_turn_squeeze_danger_over_bus():
    finals, timeline, _ = drive_over_bus(sim.by_id()["S2"])
    assert finals["RIGHT"] == "DANGER"
    assert "DANGER" in timeline["RIGHT"]          # reached DANGER on the wire, not just at the end


def test_live_F1_sensor_unplugged_goes_unknown_over_bus():
    finals, timeline, _ = drive_over_bus(sim.by_id()["F1"])
    assert "DANGER" in timeline["RIGHT"]          # detected first
    assert finals["RIGHT"] == "UNKNOWN"           # then unplugged → fail-loud over the wire


def test_live_F3_vru_escalates_over_bus():
    finals, _, _ = drive_over_bus(sim.by_id()["F3"])   # pedestrian (default cls)
    assert finals["RIGHT"] == "DANGER"


def test_live_F5_group_fire_halves_per_sensor_rate_over_bus():
    """TC-F5 on the wire: with group_fire, each ultrasonic sensor publishes ~half the ticks."""
    sc = sim.by_id()["S5"]                          # group_fire=True, static objects, 2.5 s
    _, _, counts = drive_over_bus(sc)
    n = sc.duration_ms // DT_MS + 1
    s_obj, _ = sim.build()
    ultrasonic = [g.sensor_id for g in s_obj.sensors if g.modality == "ultrasonic"]
    assert len(ultrasonic) == 8
    for sid in ultrasonic:
        assert 0.4 * n <= counts.get(sid, 0) <= 0.6 * n


def test_retained_zone_state_delivered_to_late_subscriber():
    """04 §4.1: bsw/zone/# is retained, so a late-joining HMI gets current state immediately.
    Drive S2, then attach a fresh subscriber to the same broker and confirm it receives RIGHT."""
    sc = sim.by_id()["S2"]
    sim_obj, cfg = sim.build(enable_camera=sc.enable_camera)
    svc = FusionService(cfg)
    broker = LoopbackBroker()
    clock = {"ms": 0}
    fusion_c = broker.client()
    fusion_c.on_message = lambda c, u, m: svc.handle_message(m.topic, m.payload, float(clock["ms"]), clock["ms"])
    fusion_c.subscribe(SUB_TOPICS)
    pub = broker.client()
    rng = Random(sc.seed)
    n = sc.duration_ms // DT_MS
    for tick in range(n + 1):
        clock["ms"] = tick * DT_MS
        for topic, payload in sim.scenario_tick_messages(sim_obj, sc, tick, DT_MS, ts=clock["ms"], rng=rng):
            pub.publish(topic, json.dumps(payload).encode())
        states, _ = svc.collect_tick(float(clock["ms"]), clock["ms"])
        for st in states:
            fusion_c.publish(f"bsw/zone/{st['zone_id']}", json.dumps(st).encode(), retain=True)

    late = broker.client()
    got: dict[str, dict] = {}
    late.on_message = lambda c, u, m: got.__setitem__(m.topic.split("/")[-1], json.loads(m.payload))
    late.subscribe([("bsw/zone/#", 0)])            # retained state replays on subscribe
    assert got.get("RIGHT", {}).get("severity") == "DANGER"
