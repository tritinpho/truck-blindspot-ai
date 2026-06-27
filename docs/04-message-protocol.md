# 04 — Message Protocol (the integration contract)

Everything integrates through **MQTT** topics carrying **JSON** payloads. This document is
the source of truth alongside the machine-readable schemas in [`../schemas/`](../schemas/).
Honor these and any component can be built independently.

## 4.1 Conventions

- Broker: MQTT 3.1.1 / 5.0 (Mosquitto). HMI connects via MQTT-over-WebSocket.
- Topic root: `bsw/`.
- Payloads: UTF-8 JSON. Times: `ts` = milliseconds since epoch (or monotonic boot ms on MCUs; the field `ts_kind` declares which).
- **Clocks & age (normative).** `ts` + `ts_kind` describe the **producer's** clock and are for ordering, intra-node latency, and display only. A consumer **must** compute staleness and end-to-end age from its **own local arrival time**, never by subtracting a foreign node's `ts`: RTC-less ESP32s send `monotonic_ms` (boot-relative) and a pre-NTP Pi's `epoch_ms` is itself unreliable during the boot window. See [ADR-0008](adr/ADR-0008-time-and-clock-domains.md).
- IDs: lowercase snake_case (`right_mid`, `rear_left`).
- QoS: sensor & zone streams use QoS 0 (high rate, latest-wins). Config/command use QoS 1. A
  dropped `bsw/zone/#` update is **self-healing**: the fusion engine republishes every zone at
  a fixed cadence, so a missed escalation is corrected within one tick, and the retained
  latest-state is always delivered on (re)subscribe. (For a vehicle pilot, consider QoS 1 on
  zone state.)
- Retained: `bsw/zone/#` are **retained** so a late-joining HMI immediately shows current state. Raw sensor topics are not retained.

## 4.2 Topic map

| Topic | Direction | Producer → Consumer | Purpose |
|-------|-----------|---------------------|---------|
| `bsw/sensor/{sensor_id}` | up | sensor node / sim → fusion | Raw range/presence reading |
| `bsw/detection/{sensor_id}` | up | camera node → fusion | Classified object (VRU/vehicle) |
| `bsw/vehicle` | up | vehicle adapter / sim → fusion | Turn/reverse/speed context |
| `bsw/zone/{zone_id}` | down | fusion → HMI | Consolidated zone severity (retained) |
| `bsw/health/{component}` | both | any → all | Heartbeat / fault status |
| `bsw/cmd/{target}` | down | HMI/operator → component | Config & calibration commands |

`zone_id ∈ { FRONT, FRONT_LEFT, FRONT_RIGHT, LEFT, RIGHT, REAR_LEFT, REAR_RIGHT, REAR }`
(the active set comes from [`../config/zones.example.json`](../config/zones.example.json)).

## 4.3 Messages

### 4.3.1 Sensor reading — `bsw/sensor/{sensor_id}`
```json
{
  "schema": "bsw.sensor_reading/1",
  "sensor_id": "right_mid",
  "ts": 1719400000123,
  "ts_kind": "epoch_ms",
  "modality": "ultrasonic",
  "present": true,
  "range_m": 0.82,
  "confidence": 0.9,
  "health": "ok"
}
```
- `range_m`: distance to nearest object in this sensor's field, or `null` if `present=false`.
- `health`: `ok | degraded | fault`. A node that cannot read its sensor publishes `fault`.
- The sensor does **not** know its zone — mapping happens in the fusion engine (FR-02/03).

### 4.3.2 Classified detection — `bsw/detection/{sensor_id}` (camera, phase 2)
```json
{
  "schema": "bsw.detection/1",
  "sensor_id": "cam_right",
  "ts": 1719400000150,
  "ts_kind": "epoch_ms",
  "object_class": "motorbike",
  "confidence": 0.78,
  "bbox": [0.41, 0.55, 0.62, 0.90],
  "est_range_m": 1.2,
  "ttc_s": 2.4
}
```
- `object_class ∈ { pedestrian, cyclist, motorbike, vehicle, unknown }` → drives the HMI icon and lets VRUs be weighted more dangerous.
- `confidence` (0..1): classifier confidence — **required** on a detection.
- Like a raw sensor, a camera node does **not** declare its zone. It is keyed by `sensor_id`; the fusion engine resolves `cam_right → RIGHT` via [`../config/sensors.example.json`](../config/sensors.example.json), so the modular sensor→zone mapping (FR-02/03) holds for cameras too — moving the camera is a config edit, not a firmware change.
- `ttc_s`: optional time-to-collision estimate (improvement, see [`10-improvements.md`](10-improvements.md)).

### 4.3.3 Vehicle context — `bsw/vehicle`
```json
{
  "schema": "bsw.vehicle/1",
  "ts": 1719400000100,
  "ts_kind": "epoch_ms",
  "speed_kph": 12.0,
  "gear": "drive",
  "turn_signal": "right"
}
```
- `gear ∈ { park, reverse, neutral, drive, unknown }` is the **single source of truth** for drivetrain state — "reversing" is `gear == "reverse"` (there is **no** separate `reverse` flag); `turn_signal ∈ { none, left, right, hazard }`.
- All fields optional/`unknown`-tolerant; absence degrades to "monitor all zones".

### 4.3.4 Zone state — `bsw/zone/{zone_id}` (the HMI's input, **retained**)
```json
{
  "schema": "bsw.zone_state/1",
  "zone_id": "RIGHT",
  "ts": 1719400000170,
  "severity": "DANGER",
  "object_class": "motorbike",
  "nearest_range_m": 0.82,
  "source": "fusion",
  "reason": "range<0.9 & turn_signal=right",
  "stale": false,
  "standby": false
}
```
- `severity ∈ { SAFE, CAUTION, DANGER, UNKNOWN }`.
- `stale=true` + `severity=UNKNOWN` when the contributing sensor(s) went silent (NFR-04).
- `standby`: park-standby (05 §5.4) — visuals kept, audio nagging suppressed. Fusion sets it on **every** zone each tick; the HMI keys audio suppression off it. Load-bearing for the HMI, so build a zone-state consumer expecting it.
- `reason`: human-readable trace for debugging/demos (observability, NFR-11).

### 4.3.5 Health / heartbeat — `bsw/health/{component}`
```json
{
  "schema": "bsw.health/1",
  "component": "fusion",
  "ts": 1719400000000,
  "status": "ok",
  "detail": "12 sensors active, 0 stale"
}
```
Each component publishes every ~1 s. Missing heartbeats surface as faults. Components **should** register an MQTT **Last-Will** on `bsw/health/{component}` (`status: "fault"`) so the broker announces an ungraceful disconnect immediately, rather than waiting out the freshness window ([ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)).

### 4.3.6 Command — `bsw/cmd/{target}` (QoS 1)
```json
{
  "schema": "bsw.cmd/1",
  "ts": 1719400000000,
  "op": "set_threshold",
  "args": { "zone_id": "RIGHT", "danger_m": 0.8, "caution_m": 1.5 }
}
```
`op ∈ { set_threshold, enable_zone, disable_zone, set_volume, reload_config, mute }`.

## 4.4 Versioning

Every payload carries a `schema` string `name/major`. Consumers must ignore unknown
fields (forward-compatible) and reject mismatched majors. Schema files live in
[`../schemas/`](../schemas/) and are used in contract tests. Coverage is **complete** — the
six message types (`sensor_reading`, `detection`, `vehicle`, `zone_state`, `health`, `cmd`)
**and** the two config files (`sensors_config`, `zones_config`) each have a schema — so the
L1 contract tests ([`11-evaluation-plan.md`](11-evaluation-plan.md)) validate every wire
message and both config files. The two **config** schemas are **strict**
(`additionalProperties:false` on the top level and each sensor/zone entry, `$comment`
excepted), so a misspelled key (e.g. `dangr_m`) **fails loud at load** instead of silently
falling back to a default. Wire-message schemas stay permissive (`additionalProperties:true`)
for forward-compatibility — consumers ignore unknown fields (above).

## 4.5 Why MQTT (short form)

Lightweight pub/sub, native to constrained MCUs and to browsers (over WebSocket),
retained messages give instant HMI state, and producers/consumers are fully decoupled —
which is exactly what enables sim/real parity. Full rationale: [ADR-0002](adr/ADR-0002-message-bus.md).
