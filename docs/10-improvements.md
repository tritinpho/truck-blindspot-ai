# 10 — Suggested Fixes & Improvements to the Proposal

The proposal is sound and well-scoped for a cấp trường task. These notes strengthen it
technically and de-risk delivery. Each is rated by value/effort and tied to a requirement.

## A. Safety & correctness

1. **Fail-loud on sensor loss (high value / low effort).** The original design implies
   "sensor detects → warn". It must also handle "sensor *silent*". A dead sensor must show
   `UNKNOWN`, never a false `SAFE`. → Built in as FR-14 / NFR-04 and the `stale` field.
2. **Debounce / hysteresis (high / low).** Real ultrasonic readings are noisy and objects
   hover at boundaries. Without debounce the alarm chatters and drivers lose trust. →
   [`05-warning-logic.md`](05-warning-logic.md) §5.3.
3. **Frame BSW as *advisory*, not control (high / zero).** State explicitly that BSW warns
   and never brakes/steers. Sets expectations, bounds liability, and keeps scope sane for a
   12-month academic project. → [`01-overview.md`](01-overview.md) §1.7.

## B. Driver trust (the make-or-break factor)

4. **Context-aware alerting to fight alert fatigue (high / medium).** A system that warns
   about every zone constantly gets turned off. Use turn-signal / reverse / speed to focus
   warnings (right-turn → boost right zones, etc.). This is also a genuine **novelty** worth
   highlighting for the "tính mới" / patent angle. → FR-08, [`05`](05-warning-logic.md) §5.4.
5. **Weight the right side for Vietnamese right-hand traffic (high / low).** The deadliest
   case is the right-turn motorbike squeeze. Default `risk_weight` favors `RIGHT` /
   `FRONT_RIGHT`. → [`05`](05-warning-logic.md) §5.1.
6. **Multimodal, color-blind-safe HMI (medium / low).** Don't rely on color alone; use icon
   shape, motion, and sound too. ~8% of male drivers are color-blind. → [`06`](06-hmi-design.md) §6.2.

## C. Sensing realism

7. **Be explicit about ultrasonic limits (high / low).** HC-SR04 ultrasonic is ~0.02–4 m,
   narrow cone, slow update, and weak on fast-moving targets — fine for low-speed
   maneuvers (the main use case) but **not** for highway-speed side traffic. Document this
   and keep a **radar (e.g. RCWL-0516 / 24 GHz) and camera** upgrade path. → [ADR-0004](adr/ADR-0004-sensor-modality.md).
8. **Sensor fusion when modalities combine (medium / medium).** When both ultrasonic and
   camera cover a zone, define precedence (camera classifies, ultrasonic ranges). The
   contract already separates `bsw/sensor` from `bsw/detection` to allow this.
9. **Time-to-collision over raw distance (medium / medium).** A closing object at 1.5 m is
   more dangerous than a static one at 1.0 m. Where range-rate is available, use TTC to
   escalate. Optional `ttc_s` field reserved. → [`04`](04-message-protocol.md) §4.3.2.

## D. Engineering / delivery

10. **Contract-first + sim/real parity (high / medium).** Freeze the message contract early
    so firmware, fusion, and HMI proceed in parallel, and the whole system is demoable in
    pure software before hardware arrives. This is the single biggest schedule de-risker. →
    [`04`](04-message-protocol.md), [ADR-0005](adr/ADR-0005-sim-real-parity.md).
11. **Black-box event logging (high / low).** The proposal requires a feasibility
    evaluation (Nội dung 6). Structured logs of every detection/alert make that evaluation
    evidence-based and reproducible (replay). → FR-10.
12. **Config-driven layout (high / low).** The proposal's core novelty is modular sensor
    placement — implement it literally as JSON config so "different truck / different
    layout" needs no code change. → FR-03, [`config/`](../config/).

## E. Scope guidance

13. **Stage the AI (high / zero).** Keep camera/AI classification as an explicit **phase 2 /
    optional** goal. The ultrasonic + zone + HMI core delivers value alone and fits the
    budget; AI is the differentiator for the *next* (cấp sở) round. → FR-11, [`09`](09-roadmap.md).
14. **Plan the upgrade to a real bus for the vehicle pilot (low / deferred).** Wi-Fi/MQTT is
    perfect for the prototype. A production in-vehicle build should move the sensor transport
    to **CAN** (noise immunity, determinism) while keeping MQTT for the HMI link. Noted now
    so the architecture won't fight it later.
15. **Security for the pilot stage (low / deferred).** The prototype broker is local and
    open; a vehicle pilot should enable MQTT auth/TLS. Flagged, intentionally deferred.

## Priority shortlist (do these first)

> 1, 2, 4, 7, 10, 11, 12 — all high-value, mostly low-effort, and already wired into this
> architecture. They turn a good concept into a system drivers will actually keep switched on.
