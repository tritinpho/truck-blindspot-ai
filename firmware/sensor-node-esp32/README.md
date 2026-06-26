# firmware/sensor-node-esp32 — reference sensor node (W track)

ESP32 + HC-SR04 ultrasonic node. Samples range/presence and publishes `bsw/sensor/{sensor_id}`
(`bsw.sensor_reading/1`) to the broker over Wi-Fi. Does **not** know its zone — the fusion engine
maps sensor → zone (FR-02/03). Honors the group-fire schedule (`fire_group`,
[ADR-0007](../../docs/adr/ADR-0007-sensor-firing-schedule.md)) to avoid ultrasonic cross-talk,
stamps `ts_kind: "monotonic_ms"` (no RTC; [ADR-0008](../../docs/adr/ADR-0008-time-and-clock-domains.md)),
and emits `bsw/health/{id}`.

**Owner:** firmware / HW liaison (W). **Best-effort / non-gating** — builds against the frozen
contract independently and integrates at G4. The software path to M3 does not depend on it
([16 §16.4](../../docs/16-build-plan.md)). Contract: [04-message-protocol.md](../../docs/04-message-protocol.md).
