# ADR-0007: Sensor firing schedule & realistic refresh rate

**Status:** Accepted (ratified 2026-06-26)
**Date:** 2026-06-26
**Deciders:** PI (Nguyễn Cảnh Tuấn), hardware liaison, software lead (ThS. Phó Trí Tín)

## Context
NFR-02 asks for **≥ 10 Hz** sampling per sensor and NFR-01 for **≤ 200 ms** end-to-end
latency (goal ≤ 100 ms). The prototype uses up to **eight HC-SR04-class ultrasonic** nodes
([ADR-0004](ADR-0004-sensor-modality.md)) around one truck. Two physical realities are not
yet reflected in the contracts or the §3.5 latency budget:

1. **Acoustic cross-talk.** Ultrasonic sensors firing into a shared space hear each other's
   echoes. Firing all eight at once produces phantom/incorrect ranges, worst exactly where
   adjacent cones overlap — the regions that matter most. The standard mitigation,
   round-robin / staggered triggering, **divides** the achievable per-sensor rate. Naïve
   round-robin of 8 sensors on a 10 Hz master cycle yields only ~1.25 Hz per sensor, which
   fails NFR-02 and wrecks NFR-01.
2. **Debounce vs. latency.** The fusion `confirm = 2` rule (05 §5.3) needs a *second*
   qualifying sample before escalating. At 10 Hz that is one extra ~100 ms inter-sample gap
   plus up to ~100 ms of phase offset — so worst-case **time-to-confirm alone is ~200 ms**,
   before broker + render. The §3.5 budget ("fusion incl. debounce ~50–100 ms") understates
   this, and the "goal ≤ 100 ms" is unreachable while `confirm ≥ 2` at 10 Hz.

## Decision
1. **Group-fire schedule.** Partition the sensors into **non-adjacent groups** that do not
   share an acoustic field (geometric opposites fire together) and fire one group per tick.
   With 2 groups each sensor samples at ~half the master rate. Target a master cycle that
   yields **≥ 5 Hz per ultrasonic sensor** (~10 Hz master, 2 groups), and **document 5 Hz/sensor
   as the realistic NFR-02 figure for ultrasonic**, reserving ≥ 10 Hz for radar/camera
   modalities that do not cross-talk. Grouping is config-driven via a `fire_group` field (the
   HW track owns the physical layout; software honors the order).
2. **Asymmetric, time-aware escalation.** Mirror the existing distance hysteresis (05 §5.3)
   in *time*: escalate **immediately (`confirm = 1`)** when a reading is well inside
   `danger_m` — a deep, unambiguous danger must not wait for a second sample — and keep
   `confirm = 2` only near the boundary. De-escalation stays slow (`release = 4`), biased
   toward safety. State the **danger-path** latency budget separately from the
   **boundary-path** budget.

## Options Considered

### Option A: Group-fire + time-aware escalation (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–Med (grouping config + firmware trigger order; a confirm-by-range rule in fusion) |
| Cost | Zero |
| Latency | Danger path ≤ ~150 ms; boundary path honestly ~200–250 ms |
| Realism | NFR-02 restated to a physically achievable, per-modality figure |

**Pros:** Keeps cheap ultrasonic; removes cross-talk artifacts; makes the latency claim
defensible per path; pure config + minor logic.
**Cons:** Per-sensor rate is below the original blanket 10 Hz; needs HW/SW coordination on
firing order.

### Option B: Keep 10 Hz, fire all sensors simultaneously
**Pros:** Simplest firmware.
**Cons:** Cross-talk corrupts ranges in the overlapping-cone regions that matter most; false
and missed detections; the resulting bench numbers would be dishonest.

### Option C: Coded/PWM ultrasonic or addressable modules that tolerate concurrent firing
**Pros:** Can fire together without cross-talk.
**Cons:** Pricier/more complex modules; over budget to start; better revisited with radar at
the pilot stage.

## Trade-off Analysis
Cross-talk is a hard physical constraint, not a tuning knob; pretending 8 ultrasonics deliver
a clean 10 Hz each would make the bench results — and the final report — wrong, violating the
honest-claims principle (13 §13.3). Group-firing accepts a realistic ~5 Hz/sensor, and
time-aware escalation recovers the latency that `confirm = 2` would otherwise cost on the
danger path. Both are config/logic changes that fit the budget and timeline. Higher rates
come for free when a zone is upgraded to radar/camera ([ADR-0004](ADR-0004-sensor-modality.md)),
which do not cross-talk.

## Consequences
- **Easier:** bench detection numbers become trustworthy; latency is defensible per path; the
  demo shows clean ranges instead of cross-talk noise.
- **Harder:** NFR-02 and the §3.5 latency budget must be rewritten per modality/path; firmware
  must honor a firing order; fusion needs the confirm-by-range rule.
- **Revisit when:** zones move to radar/camera (raise that zone's rate), or a faster
  MCU/trigger scheme is adopted.

## Action Items
1. [ ] Add `fire_group` (and an effective-rate note) to sensor config; HW track defines non-adjacent groups for the target truck. (Schema field already reserved in [`../../schemas/sensors-config.schema.json`](../../schemas/sensors-config.schema.json).)
2. [x] Confirm-by-range **quantified**: `immediate_danger_factor` (default 0.6) in [05 §5.3](../05-warning-logic.md) + `config` defaults — immediate escalate when `range_m ≤ factor × danger_m`. Fusion implementation lands in G3.
3. [ ] Rewrite **NFR-02** as per-modality (ultrasonic ~5 Hz/sensor, radar/camera ≥ 10 Hz) and split the **§3.5** latency budget into danger-path vs boundary-path; reconcile the NFR-01 "goal ≤ 100 ms" wording in [02-requirements.md](../02-requirements.md) and [03-architecture.md](../03-architecture.md).
4. [ ] Add to [11-evaluation-plan.md](../11-evaluation-plan.md): **TC-F5** (measure real per-sensor rate under group-firing) and a danger-path latency measurement extending the NFR-01 test.
