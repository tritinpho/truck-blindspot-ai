# 13 — Privacy & Ethics Note

BSW is a safety aid that, in its phase-2 camera configuration, observes people on the road
(pedestrians, cyclists, motorbike riders). This note states the privacy and ethical
principles the software follows. It is intentionally lightweight — proportional to a
research prototype — but written now so the design honors it from the start.

## 13.1 Principles

1. **Safety purpose only.** Sensor and camera data exist solely to warn the driver of nearby
   road users. No other use.
2. **On-device, ephemeral processing.** Camera frames are processed **on the Raspberry Pi**
   and not transmitted off the vehicle. Frames are held only transiently in memory for
   inference and then discarded.
3. **No identity capture.** The system needs an object's **class and location**
   (e.g. "motorbike, right zone, 0.8 m"), never *who* it is. It does **not** perform face
   recognition or license-plate recognition, and does not attempt to identify individuals.
4. **Minimal, non-personal logging.** The black-box event log (FR-10) stores zone severity,
   ranges, timestamps, and object **class** — not images. Raw video is **not** logged in
   normal operation.
5. **Bounded recording for development only.** If short video clips are recorded during
   bench testing to tune the detector, they are: clearly scoped to the test, stored locally,
   access-restricted, and deleted after the study. This is a research activity, not a feature.

## 13.2 Data inventory

| Data | Personal? | Retained? | Where |
|------|-----------|-----------|-------|
| Ultrasonic/radar range readings | No | Transient + in event log | Pi |
| Camera frames (phase 2) | Potentially (people visible) | **No** (transient, in-memory) | Pi RAM |
| Detections (class, bbox, range) | No (no identity) | In event log | Pi |
| Zone state / alerts | No | In event log | Pi |
| Dev tuning clips (testing only) | Potentially | Temporary, then deleted | Restricted local store |

## 13.3 Ethical considerations

- **Advisory, not autonomous.** BSW informs the driver; the driver remains fully
  responsible. The system must not encourage over-reliance — the HMI and any documentation
  state its limits (range, speed, weather; see [`10-improvements.md`](10-improvements.md) #7).
- **Honest claims.** Marketing/report claims must match measured performance from
  [`11-evaluation-plan.md`](11-evaluation-plan.md) — headline detection/latency figures come
  from **L4 bench**, not L3 sim (sim derives detection from zone geometry). No overstating
  detection ability.
- **Fail-safe transparency.** Faults are shown, not hidden (NFR-04) — drivers are never
  given false confidence.
- **Equity of detection.** During tuning, check the detector performs across rider types and
  lighting/weather common in Vietnam, so protection isn't biased toward easy cases.

## 13.4 If this becomes a product (forward-looking)

For a vehicle pilot or commercial unit, the following would need formal treatment (deferred,
flagged here):
- Compliance with Vietnamese personal-data regulations (e.g. Decree 13/2023/NĐ-CP on
  Personal Data Protection) if any imagery or identifiable data is ever stored or transmitted.
- A data-retention & access policy, secure storage, and (if a fleet/cloud feature is added)
  consent and transport security (MQTT auth/TLS — see [`10-improvements.md`](10-improvements.md) #15).
- A clear user-facing statement of what the device does and does not record.

> Bottom line for the prototype: **detect location and class, warn the driver, keep nothing
> that identifies anyone, and process everything on the vehicle.**
