# 20 — Firmware-Contract Checklist (ESP32 sensor node, G4 · W track)

**Audience:** the student building the ESP32 + ultrasonic sensor nodes.
**Promise:** if your node emits exactly the messages in this document, it plugs into the existing
pipeline with **zero downstream change** — the fusion engine and HMI already run against this same
frozen contract via the simulator (proven end-to-end through **M3**, [`18-m3-summary.md`](18-m3-summary.md)).
Your node simply becomes another producer of the *identical* bytes the simulator already publishes
(sim/real **parity**, [ADR-0005](adr/ADR-0005-sim-real-parity.md)). **You can build to this one
document without reading the rest of the repo.**

This is the **W (firmware) track** — best-effort and **non-gating**: the software path to M3 never
depended on hardware ([`16-build-plan.md`](16-build-plan.md) §16.1/§16.4). At G4 your node replaces
the simulator as the message source; nothing else moves.

> **The contract is FROZEN.** [`../schemas/`](../schemas/) + [`04-message-protocol.md`](04-message-protocol.md)
> are locked (tag `m1-contracts-frozen`); changing them needs a major version bump + an ADR. Build
> to them as-is. Everything below is *how to satisfy* the contract, not new contract.

---

## 20.0 Where your node fits

```
   ┌─────────────┐   bsw/sensor/{id}     ┌──────────────┐   bsw/zone/{zone}   ┌──────────┐
   │  ESP32 +    │  ───────────────────► │   fusion     │  ─────────────────► │  in-cab  │
   │  HC-SR04 ×N │   (Wi-Fi → broker)    │   engine     │   (retained)        │   HMI    │
   │  YOUR NODE  │   bsw/health/{node}   │ (sensor→zone │   bsw/health/fusion │ (browser)│
   └─────────────┘                       │  mapping)    │                     └──────────┘
          ▲                              └──────────────┘
          └── interchangeable with sim/geometry.py (the simulator publishes the SAME messages)
```

You own **only** the leftmost box. You publish raw range/presence; the fusion engine decides zones
and severity; the HMI draws. **Your node knows nothing about zones, thresholds, or severity** —
that intelligence is central and config-driven (FR-02/03). Moving a sensor to a different zone is a
one-line edit in [`../config/sensors.example.json`](../config/sensors.example.json) on the Pi, **not**
a firmware change.

The reference emitter you are cloning in C is [`../sim/geometry.py`](../sim/geometry.py)
(`_reading` / `_detection`) — when in doubt about a field, match what it puts on the wire.

---

## 20.1 The wire message — `bsw.sensor_reading/1` (this is the deliverable)

Publish one JSON object **per firing sensor, per sample** to `bsw/sensor/{sensor_id}`. Schema:
[`../schemas/sensor-reading.schema.json`](../schemas/sensor-reading.schema.json); prose:
[`04 §4.3.1`](04-message-protocol.md). Minify on the wire (the pretty form is for reading):

```json
{
  "schema": "bsw.sensor_reading/1",
  "sensor_id": "right_mid",
  "ts": 142037,
  "ts_kind": "monotonic_ms",
  "modality": "ultrasonic",
  "present": true,
  "range_m": 0.82,
  "confidence": 0.9,
  "health": "ok"
}
```

| Field | Type / units | Required | Rule for your node |
|-------|--------------|:--------:|--------------------|
| `schema` | const `"bsw.sensor_reading/1"` | ✅ | Exactly this string. It selects the validator. |
| `sensor_id` | string `^[a-z0-9_]+$` | ✅ | The id from `sensors.example.json` (e.g. `right_mid`). **Must equal the topic leaf.** Carries **no** zone. |
| `ts` | integer ms ≥ 0 | ✅ | Your clock in **milliseconds**. RTC-less ESP32 → `millis()` (ms since boot). See `ts_kind`. |
| `ts_kind` | `"monotonic_ms"` \| `"epoch_ms"` | ⬜ (default `epoch_ms`) | **Set `"monotonic_ms"`** — you have no RTC ([ADR-0008](adr/ADR-0008-time-and-clock-domains.md)). Omitting it makes consumers assume a wall clock you don't have. |
| `modality` | `"ultrasonic"` (here) | ⬜ (recommended) | Always send `"ultrasonic"` for HC-SR04. |
| `present` | boolean | ✅ | `true` iff an object is within `max_range_m`; else `false`. |
| `range_m` | number ≥ 0, **or `null`** | ✅* | Metres to the nearest object. **`present=false` ⇒ `range_m` MUST be `null`.** |
| `confidence` | number 0..1 | ⬜ | ~`0.9` for a clean echo; lower it if you smooth/doubt. Optional. |
| `health` | `"ok"` \| `"degraded"` \| `"fault"` | ✅ | `"ok"` normally; `"fault"` if the sensor can't be read (see §20.6). |

\* `range_m` is schema-optional but **contractually required when `present=true`** — a detected
object must carry a distance. The offline checker (§20.8) flags both halves of this rule.

**HC-SR04 → `range_m` (metres).** Echo pulse width in microseconds → metres (sound ≈ 343 m/s, round
trip, ≈ 58 µs/cm):

```c
// echo_us = pulse width measured on the ECHO pin (round trip)
float range_m = echo_us / 5800.0f;          // = (echo_us/58.0) cm / 100
bool  present = (echo_us > 0) && (range_m <= MAX_RANGE_M);   // MAX_RANGE_M = 4.0 (per config)
// present == false  →  publish range_m as JSON null, NOT 0.0 and NOT omitted
```

A no-echo timeout, an out-of-range reading (`> max_range_m`), or an implausibly short spike → treat
as **no object**: `present=false`, `range_m=null`. Do **not** publish `0.0` for "nothing there"
(0 m reads as an object touching the truck).

---

## 20.2 Topic, QoS, retain ([04 §4.1](04-message-protocol.md))

| What | Topic | QoS | Retain |
|------|-------|:---:|:------:|
| Range/presence | `bsw/sensor/{sensor_id}` | **0** | **no** |
| Node heartbeat | `bsw/health/{node_id}` | 0 | no |
| Node Last-Will | `bsw/health/{node_id}` | 1 | no |

- **Topic root is `bsw/`.** The sensor topic's leaf **is** the `sensor_id` — `bsw/sensor/right_mid`
  carries `"sensor_id":"right_mid"`. They must match (the checker verifies this when you capture with
  `-v`).
- **QoS 0, not retained** for the sensor stream: it is high-rate and latest-wins; a dropped frame is
  self-healing (the fusion engine re-publishes each zone every tick, and ages a silent sensor to
  UNKNOWN). Do **not** retain sensor readings — a retained stale range would lie to a late consumer.
- IDs are lowercase `snake_case`.

---

## 20.3 The group-fire schedule ([ADR-0007](adr/ADR-0007-sensor-firing-schedule.md))

Eight HC-SR04 firing at once hear **each other's** echoes (acoustic cross-talk) → phantom ranges,
worst exactly where adjacent cones overlap. Mitigation: split the sensors into two **non-adjacent
groups** and fire **one group per tick**, alternating. Two groups ⇒ each sensor samples at **~half**
the master rate. Target **~10 Hz master ⇒ ~5 Hz per sensor** — this is the realistic NFR-02 figure
for ultrasonic.

`fire_group` is config-driven in [`../config/sensors.example.json`](../config/sensors.example.json);
the **HW track owns the firing order**, software just honors it. The example layout:

| `sensor_id` | `zone` | `fire_group` | mount |
|-------------|--------|:------------:|-------|
| `front_center` | FRONT | **0** | front bumper center |
| `left_mid` | LEFT | **0** | left side mid |
| `right_mid` | RIGHT | **0** | right side mid *(highest risk)* |
| `rear_center` | REAR | **0** | rear bumper center |
| `front_left` | FRONT_LEFT | **1** | front-left corner |
| `front_right` | FRONT_RIGHT | **1** | front-right corner |
| `rear_left` | REAR_LEFT | **1** | rear-left corner |
| `rear_right` | REAR_RIGHT | **1** | rear-right corner |

Group 0 = the four **center/mid** sensors; group 1 = the four **corner** sensors. Adjacent cones
(e.g. `front_center` and `front_left`) always land in **different** groups, so they never ping
together.

**Firing rule (one ~100 ms master tick, alternating groups):**

```c
const float MASTER_HZ = 10.0f;               // ~5 Hz per sensor across 2 groups
uint8_t tick = 0;
for (;;) {
    uint8_t group = tick & 1;                // 0,1,0,1,...
    for (each sensor s I drive)
        if (s.fire_group == group) {
            float r = read_hcsr04(s);        // trigger + measure THIS group only
            publish_reading(s, r);           // bsw/sensor/{s.id}
        }
    publish_heartbeat_if_due();              // ~1 Hz, §20.6
    tick++;
    delay_until_next_tick(MASTER_HZ);        // ~100 ms
}
```

**Topology guidance.**
- *One ESP32 multiplexing several HC-SR04 (recommended for the prototype):* fire group 0 on even
  ticks and group 1 on odd ticks exactly as above — coordination is free because one MCU owns the
  schedule.
- *Multiple ESP32s, one sensor each:* assign **whole groups to nodes** (the group-0 node fires on the
  even half-cycle, the group-1 node on the odd half-cycle) and keep their ~100 ms phases offset, so
  the two groups still never overlap. A shared phase reference (a common boot-sync or a periodic
  trigger) keeps them out of step; this sync is a HW-track detail, not part of the wire contract.

**Contract requirement (what's checked, TC-F5):** each sensor samples at **≥ ~5 Hz** (publish faster
than ~233 ms so a single drop can't trip the 700 ms staleness window), and sensors **sharing an
acoustic field never fire in the same tick**. Record your achieved per-sensor rate for the report.

---

## 20.4 Clocks — `ts_kind = "monotonic_ms"` ([ADR-0008](adr/ADR-0008-time-and-clock-domains.md))

- The ESP32 has **no RTC**. Stamp `ts` with `millis()` and declare **`ts_kind: "monotonic_ms"`**
  (ms since *your* boot). Never invent a wall-clock epoch.
- This is safe because **consumers never subtract your `ts`**. Staleness and latency are measured
  from the consumer's **own local arrival time** ([ADR-0008](adr/ADR-0008-time-and-clock-domains.md));
  your `ts` is for ordering/inspection only. So an unsynced, boot-relative clock is fine and works
  **offline and at boot** — the exact window naïve epoch timestamps fail in.
- **Optional SNTP (bench aid only, [ADR-0008](adr/ADR-0008-time-and-clock-domains.md) #4).** If the
  bench has internet you *may* SNTP-sync and switch to `ts_kind:"epoch_ms"` for human-comparable logs.
  Treat it strictly as a convenience — **never** rely on it for safety, and keep `monotonic_ms` as the
  default. Latency for the report is measured by [`../tools/latency_observer.py`](../tools/latency_observer.py)
  on a single observer clock regardless, so you do **not** need SNTP to produce headline numbers.

---

## 20.5 Transport — Wi-Fi → broker (RS-485 fallback) ([ADR-0002](adr/ADR-0002-message-bus.md))

- **Wi-Fi → MQTT** to the broker (Mosquitto) on the Pi: `mqtt://<pi-ip>:1883`. Zero harness, native
  on the ESP32 — the chosen prototype transport. Use a small MQTT client (Arduino `PubSubClient`,
  or `esp-mqtt` on ESP-IDF). Keep payloads minified.
- The broker allows anonymous connections on the dev bench
  ([`../deploy/mosquitto/mosquitto.conf`](../deploy/mosquitto/mosquitto.conf)); no auth/TLS yet
  (deferred to the vehicle pilot).
- **Fallback:** a wired **UART/RS-485** bus is the low-cost fallback if Wi-Fi jitter/dropout appears
  inside a metal truck body; CAN is the pilot-grade endpoint. Not needed for bench bring-up — noted
  so you know the escape hatch exists.
- Set a sane MQTT **keep-alive** (e.g. 5 s) so the broker times you out quickly into your Last-Will
  (§20.6) if the node drops off Wi-Fi.

---

## 20.6 Heartbeat + Last-Will + fail-loud ([04 §4.3.5](04-message-protocol.md), [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md))

**Heartbeat** — publish `bsw/health/{node_id}` ~every 1 s:

```json
{ "schema": "bsw.health/1", "component": "esp32_right", "ts": 143000,
  "ts_kind": "monotonic_ms", "status": "ok", "detail": "rssi=-58dBm, 4 sensors, 0 read-fail" }
```

`status ∈ ok | degraded | fault`; `component` = your node id and **must equal the topic leaf**
(`bsw/health/esp32_right`). `detail` is free text (RSSI, sensor count) for diagnostics.

**Last-Will (register at CONNECT, before you publish anything).** So an ungraceful drop (power loss,
Wi-Fi gone) is announced immediately instead of waiting out the freshness window:

```c
// PubSubClient: connect with a will on your health topic
client.connect(node_id,
               /*will topic*/ "bsw/health/esp32_right",
               /*will qos*/   1,
               /*will retain*/false,
               /*will msg*/   "{\"schema\":\"bsw.health/1\",\"component\":\"esp32_right\","
                              "\"ts\":0,\"ts_kind\":\"monotonic_ms\",\"status\":\"fault\","
                              "\"detail\":\"last-will: node offline\"}");
```

**Fail loud on a read failure.** If a sensor can't be read (no echo hardware response, wiring fault),
publish that sensor's reading with **`health:"fault"`, `present:false`, `range_m:null`** — never go
silent and never fake a SAFE/clear reading. The fusion engine ages a faulted/silent sensor to
**UNKNOWN** (hatched on the HMI + a one-shot fault chime) within `stale_after_ms` (700 ms) — that is
TC-F1, the safety story. A degraded-but-usable sensor (e.g. noisy) may use `health:"degraded"`.

---

## 20.7 You carry NO zone knowledge (FR-02/03)

Worth repeating because it's the project's novelty: the node publishes `sensor_id` only. The mapping
`sensor_id → zone` lives **centrally** in [`../config/sensors.example.json`](../config/sensors.example.json)
and the fusion engine builds the reverse index at load. Consequences for you:

- **Never** put `FRONT`/`RIGHT`/zone names, thresholds, or `DANGER`/`CAUTION` in firmware.
- A camera node would publish `bsw/detection/{sensor_id}` with `object_class` and likewise no zone —
  same principle (phase-2, out of scope here).
- Re-homing a sensor is a config edit on the Pi; you reflash nothing.

---

## 20.8 Offline self-check — validate a captured message (do this first)

Before integrating, prove your bytes match the frozen contract **without** the broker or any
hardware, using the **same validator CI uses** ([`../tools/validate_message.py`](../tools/validate_message.py)
— the L1 contract validator, reused from [`../tests/test_contracts.py`](../tests/test_contracts.py)).
It needs only Python + `jsonschema` + the repo `schemas/`:

```bash
pip install jsonschema

# A) validate a hand-written sample or a saved capture file:
python tools/validate_message.py my_sample.json
python tools/validate_message.py my_sample.json --strict     # also fail on convention warnings

# B) validate straight off the bus (keep the topic with -v so topic⇄sensor_id is checked too):
mosquitto_sub -h <pi-ip> -v -C 1 -t 'bsw/sensor/right_mid' | python tools/validate_message.py -
```

It checks the **schema** (hard fail, exit 1) **and** the cross-field/clock **conventions** JSON
Schema can't express (warnings, or hard fail under `--strict`): `present=false ⇒ range_m null`,
`present=true ⇒ range_m present`, `ts_kind` set to `monotonic_ms`, `health:"fault"` not paired with
`present:true`, and topic-leaf ⇄ `sensor_id` agreement.

**Known-good reference messages** to diff your output against live in
[`../tests/fixtures/firmware/`](../tests/fixtures/firmware/) (`sensor_present`, `sensor_clear`,
`sensor_fault`, `health_heartbeat`) — these validate clean and are pinned by the test suite, so they
won't rot.

```bash
python tools/validate_message.py tests/fixtures/firmware/sensor_present.json   # → PASS, 0 warnings
```

---

## 20.9 Bring-up ACCEPTANCE test (the G4 hand-off)

Goal: **your node's messages drive `bsw/zone` and the HMI reacts identically to the simulator.** That
is the whole G4 success criterion (parity, ADR-0005). No code downstream changes.

**Setup** (on the Pi / a laptop; needs no extra firmware):

```bash
# 1. bring up the broker + fusion (the existing stack, unchanged):
docker compose -f deploy/docker-compose.yml up -d
# 2. serve the HMI (or `cd apps/hmi && npm run dev`):
docker compose -f deploy/docker-compose.yml --profile hmi up -d     # → http://localhost:8080
# 3. power your ESP32 node; point it at mqtt://<pi-ip>:1883
```

**Checks:**

1. **It's on the bus, contract-valid.** `mosquitto_sub -h <pi-ip> -v -t 'bsw/sensor/#'` shows your
   readings; pipe one through `tools/validate_message.py -` → PASS (§20.8).
2. **It drives zones.** Put an object ~0.8 m into a sensor's field (e.g. `right_mid` → RIGHT). Watch
   `mosquitto_sub -h <pi-ip> -t 'bsw/zone/RIGHT'`: severity climbs `SAFE → CAUTION → DANGER` as the
   object closes. The **HMI** tints RIGHT, shows the blob + range, raises the banner, and sounds the
   escalating beep.
3. **It matches the sim.** Run the deterministic expectation for the same motion and compare:
   `python tools/scenario_runner.py S2` prints the expected `RIGHT → DANGER`, banner = RIGHT. Your
   live run should reach the same end state — that's parity.
4. **Fail-loud (TC-F1).** Unplug the sensor (or kill the node). Within ~700 ms the RIGHT zone goes
   **UNKNOWN** (hatched) + one fault chime; the node's Last-Will flips `bsw/health/{node}` to `fault`.
   Never a stale green.
5. **Rate (TC-F5).** Count ~10 s of one sensor's messages and confirm **~5 Hz** with no starved
   sensor, and that grouped (adjacent) cones aren't firing in the same tick:
   `mosquitto_sub -h <pi-ip> -t 'bsw/sensor/right_mid' | (sleep 10; kill $!) ` — expect ~50 messages.
6. **(Optional) latency.** `python tools/latency_observer.py` while you trip a zone → indicative
   danger-path end-to-end on a single observer clock. The **headline** latency/detection numbers are
   the L4-bench measurement ([`11 §11.2`](11-evaluation-plan.md)); this is the rig that produces them.

**Pass = checks 1–5 green** (6 is the bonus that starts feeding L4). At that point the simulator and
your hardware are interchangeable and the rest of the system is already done.

---

## 20.10 Conformance checklist (tick before hand-off)

**Message contract**
- [ ] Publishes `bsw/sensor/{sensor_id}` with `schema:"bsw.sensor_reading/1"`; topic leaf == `sensor_id`. (§20.1–20.2)
- [ ] `sensor_id` matches an id in `config/sensors.example.json`; **no** zone/severity anywhere in firmware. (§20.7)
- [ ] `present=true` carries a numeric `range_m`; `present=false` carries `range_m: null` (never `0.0`, never omitted). (§20.1)
- [ ] `range_m` is **metres** via `echo_us/5800`; out-of-range/no-echo ⇒ `present=false`. (§20.1)
- [ ] `health` is `ok` normally; a read failure publishes `health:"fault"`, `present:false`, `range_m:null`. (§20.6)
- [ ] `ts = millis()` and **`ts_kind:"monotonic_ms"`** (no fake epoch). (§20.4)

**Transport / scheduling**
- [ ] Connects Wi-Fi → `mqtt://<pi>:1883`; payloads minified; QoS 0, **not retained** on the sensor stream. (§20.2, §20.5)
- [ ] Honors `fire_group` (alternating groups); adjacent cones never fire together. (§20.3)
- [ ] Each sensor samples **~5 Hz** (publishes < ~233 ms apart). (§20.3)
- [ ] Heartbeat on `bsw/health/{node}` ~1 Hz; `component` == topic leaf. (§20.6)
- [ ] **Last-Will** registered at connect (`status:"fault"` on `bsw/health/{node}`). (§20.6)

**Verification**
- [ ] A captured message passes `python tools/validate_message.py - --strict` (schema **and** conventions). (§20.8)
- [ ] Output diffs clean against `tests/fixtures/firmware/*.json`. (§20.8)
- [ ] Acceptance test §20.9 checks 1–5 green: drives `bsw/zone`, HMI matches the sim, fail-loud works, ~5 Hz. (§20.9)
- [ ] Achieved per-sensor rate recorded for the report (TC-F5); optional latency capture started for L4. (§20.9)

---

## 20.11 Quick reference

- **Contract:** [`04-message-protocol.md`](04-message-protocol.md) · schema
  [`../schemas/sensor-reading.schema.json`](../schemas/sensor-reading.schema.json) ·
  health [`../schemas/health.schema.json`](../schemas/health.schema.json)
- **Mapping/config:** [`../config/sensors.example.json`](../config/sensors.example.json) (your `sensor_id`s, `fire_group`s, `stale_after_ms`)
- **Reference emitter (Python, clone its fields):** [`../sim/geometry.py`](../sim/geometry.py)
- **Self-check tool + samples:** [`../tools/validate_message.py`](../tools/validate_message.py) · [`../tests/fixtures/firmware/`](../tests/fixtures/firmware/)
- **Run the pipeline:** [`17-demo-and-run.md`](17-demo-and-run.md) · [`../deploy/docker-compose.yml`](../deploy/docker-compose.yml)
- **ADRs:** group-fire [ADR-0007](adr/ADR-0007-sensor-firing-schedule.md) · clocks [ADR-0008](adr/ADR-0008-time-and-clock-domains.md) · parity [ADR-0005](adr/ADR-0005-sim-real-parity.md) · bus [ADR-0002](adr/ADR-0002-message-bus.md) · fail-loud [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)
