"""In-process loopback MQTT bus — a broker-free stand-in for the integration shim.

Implements just the slice of the paho-mqtt API the fusion service + the scenario publisher use
(connect / subscribe / publish / loop_start / will_set / disconnect + on_connect/on_message), with
real MQTT topic-wildcard matching (`+`, `#`) and retained messages. Delivery is SYNCHRONOUS inside
`publish()` — so a run on a controlled clock is fully deterministic, no sockets, no sleeps, no flake.

This is a TEST TRANSPORT, not a forked logic path: the SAME FusionService and the SAME scenario
wire stream (sim.scenario_tick_messages) run over it as over a real broker, so it proves the live
wiring (topic routing → engine → retained bsw/zone) without a broker. The broker-backed test
(test_integration_broker.py) covers the real paho+TCP path when a broker is available.
"""
from __future__ import annotations


def topic_matches(filt: str, topic: str) -> bool:
    """MQTT topic-filter match: `+` = one level, `#` = this level and all below."""
    f, t = filt.split("/"), topic.split("/")
    for i, fp in enumerate(f):
        if fp == "#":
            return True
        if i >= len(t):
            return False
        if fp != "+" and fp != t[i]:
            return False
    return len(f) == len(t)


class _Msg:
    __slots__ = ("topic", "payload")

    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


class LoopbackBroker:
    def __init__(self):
        self.clients: list[LoopbackClient] = []
        self.retained: dict[str, bytes] = {}

    def client(self) -> "LoopbackClient":
        c = LoopbackClient(self)
        self.clients.append(c)
        return c

    def route(self, topic: str, payload: bytes, retain: bool) -> None:
        if retain:
            if payload:
                self.retained[topic] = payload
            else:
                self.retained.pop(topic, None)  # empty retained payload clears it (MQTT)
        for c in list(self.clients):
            c.deliver(topic, payload)


class LoopbackClient:
    def __init__(self, broker: LoopbackBroker):
        self.broker = broker
        self.subs: list[str] = []
        self.userdata = None
        self.on_connect = None
        self.on_message = None
        self._will: tuple[str, bytes, bool] | None = None

    # --- paho surface used by fusion + publishers ---

    def connect(self, host="localhost", port=1883, keepalive=60, *a, **k) -> int:
        if self.on_connect:
            self.on_connect(self, self.userdata, {}, 0)
        return 0

    def loop_start(self) -> None:  # synchronous bus — nothing to pump
        pass

    def loop_stop(self) -> None:
        pass

    def will_set(self, topic: str, payload=None, qos: int = 0, retain: bool = False) -> None:
        self._will = (topic, _as_bytes(payload), retain)

    def subscribe(self, topics, qos: int = 0):
        for filt in _filters(topics):
            if filt not in self.subs:
                self.subs.append(filt)
            for rt_topic, rt_payload in list(self.broker.retained.items()):
                if topic_matches(filt, rt_topic):  # retained delivery on subscribe (late HMI)
                    self.deliver(rt_topic, rt_payload)
        return (0, 0)

    def unsubscribe(self, topics):
        for filt in _filters(topics):
            if filt in self.subs:
                self.subs.remove(filt)
        return (0, 0)

    def publish(self, topic: str, payload=None, qos: int = 0, retain: bool = False):
        self.broker.route(topic, _as_bytes(payload), retain)
        return _PubResult()

    def disconnect(self, *, deliver_will: bool = False) -> None:
        """deliver_will=True simulates an ungraceful drop so the LWT fires (TC-F4 fault path)."""
        if deliver_will and self._will:
            self.broker.route(*self._will)

    # --- internal ---

    def deliver(self, topic: str, payload: bytes) -> None:
        if self.on_message and any(topic_matches(f, topic) for f in self.subs):
            self.on_message(self, self.userdata, _Msg(topic, payload))


class _PubResult:
    rc = 0

    def is_published(self) -> bool:
        return True


def _as_bytes(payload) -> bytes:
    if payload is None:
        return b""
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return payload


def _filters(topics):
    if isinstance(topics, str):
        return [topics]
    out = []
    for item in topics:
        out.append(item[0] if isinstance(item, (list, tuple)) else item)
    return out
