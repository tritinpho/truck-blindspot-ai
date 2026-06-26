"""Broker-backed integration smoke (build-plan S5 #1) — the REAL live path over paho + TCP.

Brings a scenario through an actual broker → fusion → bsw/zone, exactly as the cabin runs:
publishes the scenario's wire stream (sim.scenario_tick_messages) to the broker and subscribes to
the retained bsw/zone/# the fusion engine produces, asserting the same outcome the in-process L3
runner computes. This is the over-the-wire complement to test_integration_shim.py (which proves the
same thing broker-free and deterministically).

Environment-agnostic and self-skipping:
  * no paho installed            → skip
  * no broker on host:port       → skip ("start the broker")
  * broker up but fusion silent  → skip ("start `python -m fusion`")
So it stays green in the agent env / plain CI, and EXECUTES in the compose-based integration job
and any local run where `docker compose up` (or a manual broker + `python -m fusion`) is live.

Local run:
    docker compose -f deploy/docker-compose.yml up -d        # broker + fusion
    pytest -q tests/test_integration_broker.py
Override target with BSW_BROKER_HOST / BSW_BROKER_PORT.
"""
from __future__ import annotations

import json
import os
import socket
import time

import pytest

import sim

mqtt = pytest.importorskip("paho.mqtt.client", reason="paho-mqtt not installed")

HOST = os.environ.get("BSW_BROKER_HOST", "localhost")
PORT = int(os.environ.get("BSW_BROKER_PORT", "1883"))
# In CI's integration job (compose brings the stack up) we want a missing broker/fusion to FAIL,
# not silently skip; locally / in the agent env it skips so a no-Docker run stays green.
REQUIRE = os.environ.get("BSW_REQUIRE_BROKER") == "1"
DT_MS = 100
CONNECT_TIMEOUT_S = 3.0
FUSION_WAIT_S = 10.0


def _unavailable(msg: str):
    pytest.fail(msg) if REQUIRE else pytest.skip(msg)


def _make_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        return mqtt.Client()


def _reachable(host: str, port: int, timeout_s: float = 0.5) -> bool:
    """Fast TCP probe so a no-broker skip is instant instead of waiting out paho's connect."""
    try:
        with socket.create_connection((host, port), timeout_s):
            return True
    except OSError:
        return False


def _wait(predicate, timeout_s: float, step: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


@pytest.fixture(scope="module")
def broker():
    """A connected client, or skip if no broker is reachable."""
    if not _reachable(HOST, PORT):
        _unavailable(f"no broker at {HOST}:{PORT}; run `docker compose -f deploy/docker-compose.yml up -d`")
    client = _make_client()
    connected = {"ok": False}
    client.on_connect = lambda c, u, f, rc, props=None: connected.__setitem__("ok", True)
    try:
        client.connect(HOST, PORT, keepalive=30)
    except OSError as e:
        _unavailable(f"broker at {HOST}:{PORT} refused the connection ({e})")
    client.loop_start()
    if not _wait(lambda: connected["ok"], CONNECT_TIMEOUT_S):
        client.loop_stop()
        _unavailable(f"broker at {HOST}:{PORT} did not complete CONNACK")
    yield client
    client.loop_stop()
    client.disconnect()


@pytest.fixture(scope="module")
def fusion_alive(broker):
    """Skip unless a fusion heartbeat is heard — i.e. the fusion engine is actually running."""
    beat = {"seen": False}
    broker.message_callback_add("bsw/health/fusion",
                                lambda c, u, m: beat.__setitem__("seen", True))
    broker.subscribe("bsw/health/fusion")
    if not _wait(lambda: beat["seen"], FUSION_WAIT_S):
        _unavailable("broker up but no fusion heartbeat — start `python -m fusion` "
                     "(or `docker compose up` brings it up)")
    return True


class _ZoneCollector:
    def __init__(self):
        self.history: dict[str, list[str]] = {}
        self.latest: dict[str, dict] = {}

    def __call__(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        zid = msg.topic.split("/")[-1]
        self.history.setdefault(zid, []).append(data.get("severity"))
        self.latest[zid] = data


def _publish_scenario(client, sc):
    simu, _ = sim.build(enable_camera=sc.enable_camera)
    n = sc.duration_ms // DT_MS
    for tick in range(n + 1):
        now = int(time.time() * 1000)
        for topic, payload in sim.scenario_tick_messages(simu, sc, tick, DT_MS, ts=now):
            client.publish(topic, json.dumps(payload))
        time.sleep(DT_MS / 1000.0)
    time.sleep(0.3)  # let the last fusion tick land on bsw/zone


@pytest.mark.parametrize("sid", ["S2", "S4"])
def test_live_scenario_over_broker(broker, fusion_alive, sid):
    """Publish a scenario over the real broker; the fusion engine's retained bsw/zone/# must reach
    DANGER on the touched zone and finish where the in-process L3 runner says it should."""
    sc = sim.by_id()[sid]
    collector = _ZoneCollector()
    broker.message_callback_add("bsw/zone/#", collector)
    broker.subscribe("bsw/zone/#")

    _publish_scenario(broker, sc)

    expected = sim.run(sc)
    for zone in {tr.zone for tr in sc.tracks}:
        assert zone in collector.history, f"{sid}: never received bsw/zone/{zone}"
        assert "DANGER" in collector.history[zone], f"{sid}: {zone} never reached DANGER over broker"
        assert collector.latest[zone]["severity"] == expected.final(zone), (
            f"{sid}: {zone} live final {collector.latest[zone]['severity']} "
            f"!= in-process {expected.final(zone)}")

    broker.message_callback_remove("bsw/zone/#")
