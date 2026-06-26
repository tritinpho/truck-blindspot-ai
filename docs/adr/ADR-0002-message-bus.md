# ADR-0002: MQTT as the common message bus

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** Software team

## Context
Sensor nodes (MCUs), the fusion engine (Python), the HMI (browser), and the simulator must
exchange data in real time. We want them **decoupled** so they can be built and tested
independently, and so a simulator can stand in for real sensors transparently (sim/real
parity, [ADR-0005](ADR-0005-sim-real-parity.md)).

## Decision
Use **MQTT** (broker: **Mosquitto**) as the single integration seam, with JSON payloads and
the topic/message contract in [`../04-message-protocol.md`](../04-message-protocol.md). HMI
connects via **MQTT-over-WebSocket**.

## Options Considered

### Option A: MQTT / Mosquitto (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Cost | Free, runs on the Pi |
| Latency | Sub-10 ms locally — fine for ≤200 ms budget |
| Fit | Native on ESP32 and in browsers; pub/sub decoupling; retained messages |

**Pros:** First-class MCU + browser support; **retained** messages give a late-joining HMI
instant state; pub/sub means producers/consumers don't know each other → parity for free;
trivial to inspect/debug; ubiquitous in IoT teaching.
**Cons:** Not a hard-real-time/deterministic bus (acceptable for advisory use); needs a
broker process (light).

### Option B: Direct sockets / custom UDP protocol
**Pros:** Minimal moving parts.
**Cons:** We'd reinvent pub/sub, discovery, retained state; tighter coupling; more bugs.

### Option C: ROS 2 (DDS)
**Pros:** Powerful robotics middleware, real-time-ish.
**Cons:** Heavy to learn/run for an 8-zone advisory display; browser HMI integration is
awkward; over budget on complexity/time.

### Option D: HTTP/REST polling
**Pros:** Familiar.
**Cons:** Polling adds latency/overhead; not a fit for continuous push at ≥10 Hz.

## Trade-off Analysis
MQTT delivers ~90% of ROS 2's decoupling at ~10% of the complexity, and is the only option
that is simultaneously **MCU-friendly and browser-friendly** — which the architecture needs
because producers are MCUs and a key consumer is a web HMI. Retained messages elegantly
solve "HMI shows correct state immediately on connect".

## Consequences
- **Easier:** parallel development; transparent simulator substitution; live observability by
  subscribing to topics; simple to add a new consumer (e.g. logger).
- **Harder:** one more process (the broker) to supervise; need schema discipline (mitigated
  by [`../../schemas/`](../../schemas/) + contract tests).
- **Revisit when:** vehicle pilot needs deterministic, noise-immune sensor transport → move
  the *sensor* hop to **CAN**, keep MQTT for the HMI link ([`../10-improvements.md`](../10-improvements.md) #14).

**Note on prototype transport.** Sensor nodes reach the broker over **Wi-Fi** — zero harness,
fastest bring-up, native on the ESP32 — which is why it wins for the bench. A wired
**UART/RS-485** bus would be more deterministic and EMI-immune even at prototype stage; it was
not adopted to start only because Wi-Fi needs no wiring, and it remains a low-cost fallback if
Wi-Fi jitter/dropout appears inside a metal truck body (CAN is the pilot-grade endpoint, #14).

## Action Items
1. [ ] Mosquitto config with WebSocket listener enabled for the HMI.
2. [ ] Publish [`../../schemas/`](../../schemas/) and add contract tests in CI.
3. [ ] Decide QoS/retain per topic per [`../04-message-protocol.md`](../04-message-protocol.md) §4.1.
