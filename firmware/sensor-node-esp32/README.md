# firmware/sensor-node-esp32 — reference sensor node (W track)

ESP32 + HC-SR04 ultrasonic node. Samples range/presence and publishes `bsw/sensor/{sensor_id}`
(`bsw.sensor_reading/1`) to the broker over Wi-Fi, so it becomes another producer of the **identical**
messages the simulator already publishes — sim/real **parity** ([ADR-0005](../../docs/adr/ADR-0005-sim-real-parity.md)).
The fusion engine + HMI are already done and run against this frozen contract through **M3**; a
conforming node plugs in at **G4** with **zero downstream change**.

## ➜ Build to the checklist

**[`docs/20-firmware-contract-checklist.md`](../../docs/20-firmware-contract-checklist.md)** is the
self-contained spec + conformance checklist. It is everything you need — you can build to it without
reading the rest of the repo. It covers, concretely and copy-pastably:

- the exact wire message (every field + units), HC-SR04 → `range_m` conversion, and the
  `present=false ⇒ range_m null` rule;
- topic / QoS 0 / not-retained conventions ([04 §4.1](../../docs/04-message-protocol.md));
- the **group-fire** schedule (`fire_group` 0/1 alternate, ~5 Hz/sensor; adjacent cones never ping
  together — [ADR-0007](../../docs/adr/ADR-0007-sensor-firing-schedule.md)) mapped to the example layout;
- `ts_kind:"monotonic_ms"` (RTC-less; [ADR-0008](../../docs/adr/ADR-0008-time-and-clock-domains.md)) +
  optional SNTP;
- `bsw/health/{node}` heartbeat + MQTT **Last-Will**, and **publish `fault` on a read failure**
  ([04 §4.3.5](../../docs/04-message-protocol.md), [ADR-0006](../../docs/adr/ADR-0006-fail-loud-compute-liveness.md));
- Wi-Fi → broker, with a UART/RS-485 fallback note ([ADR-0002](../../docs/adr/ADR-0002-message-bus.md));
- a bring-up **acceptance test** (against `docker compose -f deploy/docker-compose.yml up -d`) and a
  ticky **conformance checklist**.

## ➜ Self-verify offline before you integrate

The node carries **no zone knowledge** — `sensor_id → zone` is central config (FR-02/03). Prove your
bytes match the frozen contract with the **same validator CI uses**, no broker/hardware needed:

```bash
pip install jsonschema
# diff your output against a known-good reference, or validate your own capture:
python tools/validate_message.py tests/fixtures/firmware/sensor_present.json   # → PASS
mosquitto_sub -h <pi-ip> -v -C 1 -t 'bsw/sensor/#' | python tools/validate_message.py - --strict
```

Known-good reference messages: [`tests/fixtures/firmware/`](../../tests/fixtures/firmware/).

## Status

**Owner:** firmware / HW liaison (W). **Best-effort / non-gating** — builds against the frozen
contract independently and integrates at G4. The software path to M3 does not depend on it
([16 §16.1/§16.4](../../docs/16-build-plan.md)). Hardware (ESP32 ×4, HC-SR04 ×8, 7" display) is
procured from S0 so it is on the shelf when firmware work happens.

_No firmware source is committed yet — this is the contract + checklist the student builds to. Drop
the ESP32 sketch / ESP-IDF project here when it exists._
