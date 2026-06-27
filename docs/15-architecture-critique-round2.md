# 15 — Architecture Critique, Round 2 & Dispositions

A second design-phase review, run **after** the round-1 critique ([14](14-architecture-critique.md))
and the ratification of [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md) /
[ADR-0007](adr/ADR-0007-sensor-firing-schedule.md), and immediately **before** implementation
starts. Round 1 closed the big structural defects; this pass re-read the contracts, configs,
schemas, and warning logic line-by-line looking for what would bite the *first* engineer — and
found eight concrete issues, several of them the **same defect class round 1 fixed elsewhere**
(a second source of truth; "works in sim, breaks on the bench") that simply had not been
checked in these spots. No showstoppers. All are doc/schema/config fixes landed here while the
contract is still unfrozen (pre-M1).

**Disposition legend:** ✅ Patched (this round) · 📝 New ADR · 🔭 Noted.

Severity: **P1** fix before the M1 contract freeze · **P2** reshape now while it is still prose ·
**P3** note and move on.

---

## P1 — Contract defects to fix before the M1 freeze

### R2-1. Threshold-scaling direction was unspecified, and the prose contradicted the configs ✅
**Problem.** The most safety-critical rule. [05 §5.4](05-warning-logic.md) said a right
turn-signal gives "**lower thresholds**"; [05 §5.2](05-warning-logic.md) said a VRU gets a
"**closer effective threshold**". But [`zones.example.json`](../config/zones.example.json)
encodes both as multipliers **> 1** (`factor_danger_m: 1.3`, `vru_threshold_multiplier: 1.25`),
and a zone triggers when `range ≤ danger_m` — so to warn *sooner* you must **widen** the
threshold (multiply: 0.8 → 1.04 m). "Lower" / "closer" are backwards from the stated intent
("escalates sooner", §5.7 / TC-F3). With the multiply-vs-divide semantics never written down,
an implementer had a coin-flip chance of making the deadly right-turn case *less* sensitive.
**Fix (applied).** Added a **normative threshold-scaling convention** to [05 §5.4](05-warning-logic.md):
`effective_threshold_m = base × factor`; factor **> 1 widens** (warns sooner), **< 1** narrows;
"boosted" = a **larger** threshold. Reworded the turn-signal row ("wider thresholds → earlier
warning") and the VRU sentence in §5.2 ("a **wider** effective threshold … escalates *sooner*").

### R2-2. `bsw/vehicle` had two sources of truth for "is the truck reversing" ✅
**Problem.** [`vehicle-context.schema.json`](../schemas/vehicle-context.schema.json) carried
both `gear` (enum includes `reverse`) **and** a separate boolean `reverse`; [05 §5.4](05-warning-logic.md)
keyed off the boolean. `{gear:"reverse", reverse:false}` was a legal, contradictory message
with undefined behavior — the dual-source defect round 1 fixed for sensor→zone (#1) and the
camera (#2), missed here.
**Fix (applied).** `gear` is the single source of truth; the boolean `reverse` was **removed**
from the schema and the [04 §4.3.3](04-message-protocol.md) example/prose; "reversing" is
`gear == "reverse"`. [05 §5.4](05-warning-logic.md) row re-keyed to `gear = reverse`.

### R2-3. Cross-clock staleness & latency broke on the bench while passing in sim 📝✅
**Problem.** [03 §3.8](03-architecture.md) said "all messages carry a **monotonic** `ts` …
fusion uses **message age** for staleness," i.e. `now − msg.ts`. But RTC-less ESP32s send
`monotonic_ms` (boot-relative) and a pre-NTP Pi's `epoch_ms` is itself wrong at boot, so
subtracting a foreign node's `ts` is meaningless — it only works in the single-process sim.
The NFR-01 latency *measurement* had the same flaw (can't subtract an ESP32 publish-`ts` from
an HMI render-`ts`). Same "sim hides hardware reality" class as [14 §P2 #6/#7](14-architecture-critique.md).
**Fix (applied).** New **[ADR-0008](adr/ADR-0008-time-and-clock-domains.md)**: staleness/liveness
are measured from **local arrival time**, never a foreign `ts`; latency is measured at a
**single observer** (SNTP-sync demoted to an optional bench aid). Corrected [03 §3.8](03-architecture.md),
added a "Clocks & age (normative)" rule to [04 §4.1](04-message-protocol.md), and the
clock caveat to the [11 §11.3](11-evaluation-plan.md) latency row.

### R2-4. The config schemas permitted silent typos, contradicting "fails loud at load" ✅
**Problem.** [04 §4.4](04-message-protocol.md) promised "a malformed config fails loud at
load," but [`sensors-config`](../schemas/sensors-config.schema.json) and
[`zones-config`](../schemas/zones-config.schema.json) set `additionalProperties: true`
everywhere — so `dangr_m: 0.5` validated and silently fell back to the default.
**Fix (applied).** Both **config** schemas are now **strict** (`additionalProperties: false` on
the top level and each sensor/zone entry, `$comment` excepted); the free-form tuning bags
(`defaults`, `context`, `alerting`) stay open. Wire-message schemas stay permissive for
forward-compatibility. [04 §4.4](04-message-protocol.md) restated honestly. Verified: the
example configs still validate, and a misspelled `dangr_m` is now rejected.

---

## P2 — Logic gaps the first unit/bench test would hit

### R2-5. `confirm-by-range` had no quantified cutoff anywhere ✅
**Problem.** ADR-0007 ratified "immediate escalate when *well inside* `danger_m`," but
"well inside / ≪" never became a number or a config field — the fusion engineer could not build
the danger-path.
**Fix (applied).** Added **`immediate_danger_factor`** (default `0.6`) to the config defaults
and [05 §5.3](05-warning-logic.md): escalate immediately (`confirm = 1`) when
`range_m ≤ immediate_danger_factor × danger_m`. Closed [ADR-0007](adr/ADR-0007-sensor-firing-schedule.md)
action #2.

### R2-6. Severity was undefined when all sensors were healthy but detected nothing ✅
**Problem.** [05 §5.2](05-warning-logic.md) computed `nearest = min(range of present, healthy
sensors)`; if all were healthy with `present=false`, that is `min(∅)` and the `UNKNOWN` branch
did not apply (they *are* reporting). The intended answer (SAFE) was never written.
**Fix (applied).** §5.2 now states the empty-present case explicitly: healthy + none present ⇒
**SAFE** (`nearest = +∞`).

### R2-7. The stale → UNKNOWN transition had no debounce → fault-chime spam ✅
**Problem.** §5.3 debounced severity but flipped straight to UNKNOWN on one stale tick, firing
the one-shot fault chime. With `stale_after_ms: 500` (≈ 2.5 ultrasonic periods) and Wi-Fi
jitter in a metal body ([ADR-0002](adr/ADR-0002-message-bus.md)), zones — and the chime — would
flicker, a trust-killer (NFR-09).
**Fix (applied).** Added a **stale-debounce** rule to [05 §5.3](05-warning-logic.md):
`stale_confirm` consecutive missed windows (default 2) before UNKNOWN, and a rate-limited
chime (`fault_chime_min_interval_ms`, default 10 s, one limiter shared across all zones).
Relaxed the example `stale_after_ms`
to **700 ms** (≥ 3× the 5 Hz sample period) and documented the rule in the schema. New tunables
in the `alerting` config block and [05 §5.8](05-warning-logic.md).

### R2-8. The two open round-1 follow-throughs weren't applied — and they gate what gets built ✅
**Problem.** [14](14-architecture-critique.md) #6/#7 were still unchecked. The eval plan
([11 §11.3](11-evaluation-plan.md)) still let the headline "Detection rate ≥ 95%" come from
**L3 sim** (which measures geometry against itself), and class-dependent features weren't tagged
phase-2 — so [FR-06](02-requirements.md) read as **Must** while its class behavior only exists
in the phase-2 camera.
**Fix (applied).** [11](11-evaluation-plan.md) now requires **L4-bench** sourcing for headline
detection/latency (L3 indicative only); [13 §13.3](13-privacy-ethics.md) honest-claims points at
L4. Added a **Phase-1 vs phase-2** note to [02](02-requirements.md) and clarified [FR-06](02-requirements.md)
and [06 §6.2](06-hmi-design.md): phase-1 ultrasonic renders a generic blob with uniform
thresholds; class icons + VRU weighting are phase-2. Round-1 checklist #6/#7 ticked.

---

## P3 — Worth a sentence, handled inline 🔭✅

- **`turn_signal = hazard`** was a legal enum value with no rule. Now defined in [05 §5.4](05-warning-logic.md):
  treated as **both** sides boosted.
- **Speed-band gap.** Config had two thresholds (`low_max 30`, `high_min 50`) but the prose used
  one (~30). [05 §5.4](05-warning-logic.md) now defines all three bands, including the 30–50
  transition (hold low-speed behavior, no abrupt change).
- **Mixed-modality precedence** ([ADR-0004](adr/ADR-0004-sensor-modality.md) action #3, was open):
  the within-zone merge for a multi-sensor zone is now specified in [05 §5.2](05-warning-logic.md)
  (range = min over present healthy; class from the camera; UNKNOWN only if all contributors
  stale). Action #3 closed.
- **MQTT Last-Will.** [04 §4.3.5](04-message-protocol.md) now recommends an LWT on
  `bsw/health/{component}` so the broker announces an ungraceful death immediately instead of
  waiting out the freshness window (complements [ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)).

---

## Follow-through checklist (round 2)

- [x] R2-1 threshold-scaling convention + reworded turn-signal/VRU (05 §5.2, §5.4)
- [x] R2-2 dropped `reverse` boolean; `gear` authoritative (vehicle schema, 04 §4.3.3, 05 §5.4)
- [x] R2-3 **ADR-0008**; local-arrival staleness + single-observer latency (03 §3.8, 04 §4.1, 11 §11.3)
- [x] R2-4 strict config schemas (`additionalProperties:false`, `$comment` excepted); 04 §4.4 restated; validated
- [x] R2-5 `immediate_danger_factor` (0.6) in config + 05 §5.3; ADR-0007 #2 closed
- [x] R2-6 empty-present ⇒ SAFE in 05 §5.2
- [x] R2-7 stale-debounce + chime rate-limit (05 §5.3/§5.8, configs, sensors schema); stale window 500 → 700 ms
- [x] R2-8 L4-bench headline sourcing (11, 13); phase-1/phase-2 tagging (02, 06); round-1 #6/#7 ticked
- [x] P3 hazard rule, speed-band gap, mixed-modality precedence (ADR-0004 #3), MQTT LWT

**Net for implementation:** the M1 contracts (schemas + [04](04-message-protocol.md)) and the
warning-logic spec ([05](05-warning-logic.md)) are now unambiguous on the points an engineer
hits first — threshold direction, clock/age, config validation, the confirm/stale/empty edge
cases — so the G3 build can proceed against a frozen, self-consistent contract.
