# ADR-0004: Sensor modality strategy

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** PI, hardware liaison, software lead

## Context
The proposal allows multiple sensor types (ultrasonic, radar, camera, IR, or combinations).
We must pick a starting modality that fits the budget and the low-speed maneuver use case,
without painting the architecture into a corner for better sensors later.

## Decision
Start the prototype with **ultrasonic (HC-SR04 class)** sensor nodes for distance/presence,
and design the contract so **radar** and **camera** can be added per zone without changing
the fusion engine or HMI. Camera-based **classification** is an explicit phase-2 add-on for
the highest-risk zone (right / front-right).

## Options Considered

### Option A: Ultrasonic first, radar/camera as upgrades (chosen)
| Dimension | Assessment |
|-----------|------------|
| Cost | Lowest (~25k VND/sensor) |
| Range/Use | ~0.02–4 m, narrow cone, low-speed — matches start-off/turn/reverse cases |
| Limits | Weak on fast/lateral targets, weather-sensitive |
| Path | Contract allows radar/camera later with no downstream change |

**Pros:** Cheapest path to a working multi-zone demo; simple; great for teaching; covers the
primary low-speed scenarios (S1–S6).
**Cons:** Not suitable for highway-speed side traffic; no object classification.

### Option B: Radar-only (24 GHz / RCWL / mmWave)
**Pros:** Better range, motion detection, weather-robust.
**Cons:** Higher cost/complexity; some cheap modules give presence not precise range;
overkill to start.

### Option C: Camera-only (vision)
**Pros:** Rich classification (pedestrian/cyclist/motorbike).
**Cons:** Needs AI + good lighting; no direct range; heaviest to get reliable; best as a
*complement*, not the sole sensor.

## Trade-off Analysis
Ultrasonic gets a complete, demoable, multi-zone system into the team's hands cheaply and
quickly, which de-risks the schedule. Because sensors are decoupled behind the message
contract ([ADR-0002](ADR-0002-message-bus.md)) and carry a `modality` field, upgrading a
zone to radar or adding a classifying camera is additive — the fusion engine already merges
`bsw/sensor` (range) and `bsw/detection` (class).

## Consequences
- **Easier:** cheap fast start; clear teaching artifact; honest about limits.
- **Harder:** must clearly document ultrasonic's speed/range limits so claims stay credible
  ([`../10-improvements.md`](../10-improvements.md) #7); fusion of mixed modalities needs
  precedence rules when both cover a zone.
- **Revisit when:** targeting higher-speed lane-change protection or VRU classification →
  add radar/camera to the relevant zones.

## Action Items
1. [ ] Reference ESP32 + HC-SR04 firmware emitting `bsw.sensor_reading`.
2. [ ] Document per-modality field-of-view & limits in sensor config.
3. [x] Define ultrasonic+camera precedence for shared zones (camera classifies, ultrasonic ranges) — specified in [05 §5.2](../05-warning-logic.md) (round 2, [15](../15-architecture-critique-round2.md)).
