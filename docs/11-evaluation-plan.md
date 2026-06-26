# 11 — Evaluation & Test Plan

This plan turns the proposal's required feasibility assessment (Nội dung 6 / Giai đoạn 5 —
*đánh giá tính khả thi*) into concrete, repeatable tests with pass/fail criteria. It is both
an engineering test plan and a source of evidence for the final report (Giai đoạn 6).

## 11.1 Objectives

1. Verify the system meets its functional and non-functional requirements
   ([`02-requirements.md`](02-requirements.md)).
2. Quantify warning quality — does it warn correctly, in time, without crying wolf?
3. Assess driver-perceived usability (the make-or-break factor, NFR-08/09).
4. Produce reproducible evidence (logs, metrics) for the academic report and the follow-on
   (cấp sở / enterprise) proposal.

## 11.2 Test levels

| Level | What | How | When |
|-------|------|-----|------|
| **L1 Contract tests** | Every message validates against [`../schemas/`](../schemas/) | Automated schema validation in CI | Continuous |
| **L2 Unit/logic tests** | Severity, debounce, context rules (`05-warning-logic.md`) | Feed synthetic readings to the fusion engine, assert zone outputs | Continuous |
| **L3 Scenario (sim) tests** | End-to-end S1–S6 through broker→fusion→HMI | Python scenario runner replays scripted scenes deterministically | Per build / regression |
| **L4 Bench (HW) tests** | Real ESP32 + ultrasonic on the model truck | Move objects through zones, record logs | Giai đoạn 4–5 |
| **L5 Usability review** | Drivers + experts judge the HMI | Structured glance-test + questionnaire | Giai đoạn 5 |

L1–L3 need no hardware (sim/real parity, [ADR-0005](adr/ADR-0005-sim-real-parity.md)), so most
evaluation runs continuously from Giai đoạn 3. **However**, the **headline** detection and
latency figures for the report must come from **L4 bench**, not L3 sim — the simulator derives
detection from zone geometry and would measure the model against itself
([14 §P2](14-architecture-critique.md) #6). L3 is for regression and logic validation.

**L3 is realized in two layers (S5).** (a) *In-process* — the scenario runner drives the real
fusion engine directly (`tests/test_scenarios.py`); (b) *over the bus* — an **integration shim**
runs the real fusion **transport** (`FusionService`) and the real scenario wire stream over an
in-process loopback bus and asserts the wired path (publisher → broker → fusion routing → retained
`bsw/zone/#` → subscriber) reproduces the same outcomes (`tests/test_integration_shim.py`), plus a
**broker-backed** test over real MQTT (`tests/test_integration_broker.py`). **CI** runs (a) + the
shim on every push (no broker, deterministic) and the broker-backed test in a job that brings up the
shipped `deploy/docker-compose.yml` (broker + fusion). See [`18-m3-summary.md`](18-m3-summary.md).

## 11.3 Metrics & acceptance criteria

| Metric | Definition | Target (pass) | Source |
|--------|------------|---------------|--------|
| **Detection rate** | % of object-in-zone events that produce the correct zone alert | ≥ 95% — **headline from L4 bench**; L3 sim indicative only (sim derives detection from zone geometry, [14 §P2](14-architecture-critique.md) #6) | L4 logs |
| **End-to-end latency (danger-path)** | object well inside `danger_m` → warning visible/audible | ≤ 200 ms (stretch ≤ 150 ms); boundary-path ≤ ~250 ms. **Headline from L4 bench**, measured at a **single observer** (or SNTP-synced nodes) — ESP32 `monotonic_ms` and Pi `epoch_ms` are not subtractable ([ADR-0008](adr/ADR-0008-time-and-clock-domains.md)) | NFR-01, ADR-0007, timestamped logs |
| **False-positive rate** | alerts with no real object in zone, per minute of driving | ≤ a tuned threshold; low enough drivers keep it on | NFR-09 |
| **Zone-localization accuracy** | % of alerts shown in the correct zone | ≥ 98% | NFR-08 |
| **Glance-time to locate** | time for a driver to name the active zone | ≤ 1 s in ≥ 95% of trials | NFR-08, L5 |
| **Flicker** | spurious severity transitions per stable object per minute | ≈ 0 (debounce holds) | FR-09, logs |
| **Fault visibility** | a disconnected sensor shown as UNKNOWN (never SAFE) | 100% | NFR-04, fault-injection |
| **Compute liveness** | whole-Pi/fusion freeze shown as UNKNOWN, not stale-green | 100% within freshness window | FR-15, ADR-0006, TC-F4 |
| **Refresh rate** | HMI redraw; ultrasonic per-sensor under group-fire | HMI ≥ 10 Hz; ultrasonic ~5 Hz/sensor | NFR-02, ADR-0007 |
| **Recovery** | auto-restart after a component crash | < 5 s | NFR-03 |

## 11.4 Scenario test cases (map to `02-requirements.md` §2.3)

Each scenario is scripted in the simulator and (later) reproduced on the bench.

| ID | Scenario | Stimulus | Expected result |
|----|----------|----------|-----------------|
| TC-S1 | Pull-away, motorbike in FRONT_RIGHT | object at 0.8 m, signal=none | FRONT_RIGHT → DANGER ≤200 ms, fast beep |
| TC-S2 | **Right turn squeeze** | motorbike along RIGHT at 0.8 m, signal=right | boosted thresholds + VRU weighting → DANGER fast; primary-alert banner = RIGHT |
| TC-S3 | Left lane change | vehicle in LEFT/REAR_LEFT, signal=left | left zones boosted → CAUTION/DANGER as range closes |
| TC-S4 | Reversing | pallet at 0.5 m REAR, gear=reverse | rear zones boosted → REAR DANGER, continuous tone |
| TC-S5 | Dense urban crawl | objects in 3+ zones | all shown; audio follows worst risk_weight×severity; no overload |
| TC-S6 | Parked by a wall | static object LEFT, gear=park, stationary | standby: LEFT amber visual, **audio silent** (no nagging) |
| TC-F1 | Sensor unplugged | RIGHT sensor stops publishing | RIGHT → UNKNOWN (hatched) + one-shot fault chime |
| TC-F2 | Boundary jitter | object oscillating at danger_m ± noise | debounce holds; ≈0 flicker |
| TC-F3 | VRU vs vehicle | pedestrian vs car at same range | pedestrian escalates sooner (VRU multiplier) |
| TC-F4 | Compute freeze | kill/suspend the fusion process or the whole Pi | map → UNKNOWN + "SIGNAL LOST" within the freshness window; "alive" pip stops (FR-15, ADR-0006) |
| TC-F5 | Ultrasonic group-fire | 8 sensors firing in 2 non-adjacent groups | each sensor samples ≥ ~5 Hz; no cross-talk phantom ranges in overlapping cones (ADR-0007) |

## 11.5 Usability review protocol (L5)

- **Participants:** ≥ 5 truck drivers + ≥ 2 domain experts (traffic safety / automotive).
- **Method:** seated in front of the HMI running scripted scenarios; for each, measure
  time-to-name-the-zone and correctness; then a Likert questionnaire (clarity, trust,
  perceived false-alarm annoyance, willingness to keep it on).
- **Output:** glance-time distribution, correctness %, qualitative themes, prioritized
  HMI refinements feeding back into Giai đoạn 5.

## 11.6 Test data & reproducibility

- All runs emit structured logs (FR-10) → SQLite/JSONL.
- The same log can be **replayed** through the pipeline (`tools/` log-replay) to recompute
  metrics deterministically — so results in the report are reproducible, not anecdotal.
- Threshold sweeps (via `bsw/cmd/set_threshold`) are logged so the chosen operating point
  is justified with data, not guesswork (NFR-09).

## 11.7 Exit criteria (project-level)

The feasibility evaluation is considered **successful** when: all M/Must requirements pass
L1–L4, the L5 usability targets are met, and the data supports a credible operating point
(detection vs false-alarm). Gaps are documented as known limitations + next-step
recommendations in the final report.
