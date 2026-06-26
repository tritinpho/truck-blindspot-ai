# 14 — Architecture Critique & Dispositions

A design-phase review of the foundational documents (01–13), the ADRs, the config files, and
the message schemas against the source proposal (*Phiếu đề xuất — Cảnh báo điểm mù xe tải*).
The package is strong: contract-first, end-to-end traceable, honest about being **advisory,
not actuating**, and the sim/real-parity bet is the right schedule de-risker. This document
records where the docs were nonetheless internally inconsistent, quantitatively optimistic, or
silent on a failure mode that matters — and what was done about each.

> **Update (round 2):** a second review after the ADR-0006/0007 ratification is recorded in
> [15-architecture-critique-round2.md](15-architecture-critique-round2.md); its eight fixes are
> applied across the contracts and docs (and added [ADR-0008](adr/ADR-0008-time-and-clock-domains.md)).

**Disposition legend:** ✅ Patched (this revision) · 📝 Proposed ADR (awaits PI sign-off) ·
🔭 Noted (no change yet).

Severity: **P1** fix before the M1 contract freeze · **P2** reshape now while it is still prose ·
**P3** note and move on.

---

## P1 — Contract & consistency defects

### 1. Two sources of truth for the sensor↔zone mapping ✅
**Problem.** [05-warning-logic.md](05-warning-logic.md) §5.1 said each *zone* carries
`sensor_ids` (zone→sensors), while [`config/zones.example.json`](../config/zones.example.json)
has no such field and [`config/sensors.example.json`](../config/sensors.example.json) puts a
`zone` on each *sensor* (sensor→zone). Invisible at one-sensor-per-zone; ambiguous the moment
§5.2's `min(range…)` aggregates two sensors into one zone.
**Fix (applied).** Sensor→zone is now the single source of truth (`sensor.zone`); the engine
builds the reverse index at load. The `sensor_ids` language was removed from §5.1.

### 2. The camera path violated the project's own core novelty ✅
**Problem.** The headline *tính mới* is central, config-driven sensor→zone mapping — "the
sensor does **not** know its zone" (FR-02/03). Yet `bsw/detection/{zone_id}` keyed detections
by **zone**, baking the camera's zone into firmware/topic. Moving the camera meant a firmware
change, exactly what the architecture promises to avoid.
**Fix (applied).** Detections are now keyed by `sensor_id` (`bsw/detection/{sensor_id}`); the
fusion engine resolves `cam_right → RIGHT` via `sensors.json` like any sensor. Updated:
[`schemas/detection.schema.json`](../schemas/detection.schema.json),
[04-message-protocol.md](04-message-protocol.md) §4.2/§4.3.2, and the camera comment in
`sensors.example.json`. *(This is a contract change; it is safe only because the contract is
not yet frozen — it must land before M1.)*

### 3. Schema coverage did not match the "every message validates" claim ✅
**Problem.** L1 contract tests assert all messages validate, but `schemas/` covered only
sensor-reading, zone-state, vehicle-context, detection — nothing for `bsw/health`, `bsw/cmd`,
or the two config files (which self-declare a `schema` string with nothing to check).
**Fix (applied).** Added [`health.schema.json`](../schemas/health.schema.json),
[`cmd.schema.json`](../schemas/cmd.schema.json),
[`sensors-config.schema.json`](../schemas/sensors-config.schema.json),
[`zones-config.schema.json`](../schemas/zones-config.schema.json); [04 §4.4](04-message-protocol.md)
now states coverage is complete (6 messages + 2 config files).

---

## P1 — Quantitative realism: the latency / refresh budget does not close

### 4. The debounce `confirm` counter blows the latency budget; ≤ 100 ms is unreachable ✅
**Problem.** [03-architecture.md](03-architecture.md) §3.5 budgets "fusion incl. debounce
~50–100 ms," but `confirm = 2` at 10 Hz needs a second qualifying sample — a full ~100 ms gap
plus up to ~100 ms phase offset — so time-to-confirm alone is ~200 ms before broker + render.
Worst case lands ~250–300 ms (> the 200 ms ceiling); the "goal ≤ 100 ms" is impossible while
`confirm ≥ 2` at 10 Hz.
**Disposition.** **ADR-0007** proposes time-aware asymmetric escalation: immediate
(`confirm = 1`) when range is well inside `danger_m`, `confirm = 2` only near the boundary;
split the §3.5 budget into danger-path vs boundary-path. **ADR-0007 ratified 2026-06-26**;
NFR-01 + §3.5 rewritten and confirm-by-range added to [05 §5.3](05-warning-logic.md).

### 5. Ultrasonic cross-talk makes per-sensor 10 Hz physically hard; no one owns the firing order ✅
**Problem.** Eight HC-SR04-class sensors firing into a shared acoustic space interfere; the
standard round-robin mitigation **divides** the per-sensor rate (~1.25 Hz naïvely), failing
NFR-02 and NFR-01. The constraint is absent from [ADR-0004](adr/ADR-0004-sensor-modality.md)
and the NFRs, and looks fine in sim while biting on the bench.
**Disposition.** **ADR-0007 ratified 2026-06-26.** Config-driven group-fire schedule
(centers vs corners, ~5 Hz/sensor) now in [`sensors.example.json`](../config/sensors.example.json)
via `fire_group`; NFR-02 restated per modality; TC-F5 added.

---

## P2 — Sensing physics the simulator will hide

### 6. Eight narrow cones do not tile the perimeter; the sim's detection rate is near-tautological 🔭
**Problem.** 30–40° cones at 4 m leave angular gaps between zones; an object can fall between
two cones and register on neither. The simulator derives detection from zone polygons / FOV
geometry, so it reports coverage the real cones lack. Consequently the **"detection rate
≥ 95%" measured in L3 (sim) mostly checks the geometry against itself**, not whether ultrasonic
finds a pedestrian's leg.
**Disposition (recommended).** Add a rule to [11-evaluation-plan.md](11-evaluation-plan.md)
and [13 §13.3](13-privacy-ethics.md): **headline detection/latency figures must come from L4
bench, not L3 sim.** L4 is on the critical path (months 8–10) with the least slack — protect it.
Optionally model cone gaps + missed-detection probability in the simulator so sim numbers stop
being optimistic.

### 7. The VRU / classification half of the warning logic is inert in the delivered system 🔭
**Problem.** FR-06 icons-by-class, `vru_threshold_multiplier`, TC-F3, and the §5.6 priority
math all depend on `object_class`, which **only the phase-2 camera produces**. The phase-1
ultrasonic system actually demoed at cấp trường sees every object as a generic blob, so a real
slice of the documented sophistication never fires — yet the docs read as one coherent system.
**Disposition (recommended).** Tag every class-dependent feature explicitly *phase-2* in
[02-requirements.md](02-requirements.md) and [06-hmi-design.md](06-hmi-design.md), and ensure
the eval plan cannot report VRU-weighting results from sim as system capability.

---

## P2 — Safety failure modes the architecture was silent on

### 8. A frozen Pi showing a stale-green display had no defense ✅
**Problem.** FR-14/NFR-04 handle a *sensor* going silent, but broker + fusion + kiosk + log all
run on one Pi. If the **Pi** hangs (kernel/SD/Chromium), the kiosk holds its last frame —
possibly all-green — with no watchdog. systemd auto-restart (NFR-03) cannot recover a kernel/SD
hang. For an advisory device, false confidence from a frozen screen is the worst case.
**Disposition.** **ADR-0006 ratified 2026-06-26.** Hardware watchdog + end-to-end HMI liveness
clock (whole map → UNKNOWN + "SIGNAL LOST" on freshness timeout) + always-animating "alive" pip,
turning the dangerous freeze into the safe UNKNOWN the design already handles. **FR-15** and
**TC-F4** added; HMI behavior in [06 §6.5](06-hmi-design.md), watchdog in NFR-03 / [03 §3.6](03-architecture.md).

### 9. Boot time vs. the pull-away scenario ✅
**Problem.** S1 (pull-away right after ignition) is top-priority, yet a Pi + Chromium cold boot
is ~20–40 s — the system may be absent during the exact maneuver, with no "not ready" signal.
**Disposition.** **ADR-0006 ratified 2026-06-26.** "Warming up — not yet monitoring" startup
screen added ([06 §6.5](06-hmi-design.md)); **NFR-12** (boot-to-monitoring budget) added;
consider keeping the Pi on accessory power.

---

## P3 — Worth a sentence, not a redesign 🔭

- **Wi-Fi sensor transport on the bench.** [ADR-0002](adr/ADR-0002-message-bus.md) defers CAN to
  the pilot, but even the prototype's 8 ESP32s over Wi-Fi inside a metal body will jitter. A
  wired **UART/RS-485** bus was never weighed for the prototype and would be cheaper to debug
  and more deterministic. At least record why Wi-Fi won for the bench.
- **QoS 0 on retained zone messages** ([04 §4.1](04-message-protocol.md)) means a `DANGER`
  escalation can be silently dropped under load until the next fixed-cadence republish.
  Self-healing, but say so explicitly for a safety signal.
- **Sub-zone icon position.** The proposal's "hiển thị biểu tượng… tại vị trí tương ứng" implies
  placing the object *within* the zone, but `zone_state` carries only severity + nearest range,
  so the HMI can only render at the zone centroid. Defensible (8-zone model) — note the fidelity
  gap so reviewers are not surprised.
- **Strategic framing of the novelty.** Config-driven sensor→zone mapping is standard in
  commercial BSD/around-view systems — thin prior-art ground for the *sáng chế* angle. The
  genuinely defensible differentiator is the **context-aware anti-alert-fatigue logic**
  ([05 §5.4](05-warning-logic.md)). Consider foregrounding it as the headline novelty in
  [01-overview.md](01-overview.md).

---

## Follow-through checklist

- [x] #1 sensor→zone single-sourced (05 §5.1)
- [x] #2 detections keyed by `sensor_id` (schema + 04 + config)
- [x] #3 added health / cmd / sensors-config / zones-config schemas (04 §4.4)
- [x] Ratify **ADR-0006** → applied FR-15, NFR-12, TC-F4; watchdog + liveness pip + warm-up screen (ratified 2026-06-26)
- [x] Ratify **ADR-0007** → restated NFR-01/02, split §3.5 latency budget, `fire_group` + confirm-by-range, TC-F5 (ratified 2026-06-26)
- [x] #6 require L4-bench (not L3-sim) sourcing for headline metrics (11, 13) — applied in round 2 ([15](15-architecture-critique-round2.md))
- [x] #7 tag class-dependent features phase-2 (02, 06) — applied in round 2 ([15](15-architecture-critique-round2.md))
- [x] #4/#5/#8/#9 doc edits landed with the ADR ratification
- [x] P3 items: one-line notes added (ADR-0002 Wi-Fi rationale; 04 §4.1 QoS-0 caveat; 06 centroid caveat; 01 novelty framing)
