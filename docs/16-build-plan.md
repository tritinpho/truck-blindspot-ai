# 16 — Build Plan: G2 Foundation → G3 (to M3)

Task-level execution plan that turns [`09-roadmap.md`](09-roadmap.md)'s phase view into
concrete sprints. **Scope:** from **M1 (contracts frozen)** through **M3 (full pipeline running
scenarios S1–S6 in simulation)** — the linchpin milestone. Design is complete (docs 01–15,
ADR-0001…0008); the contract is frozen; **no code exists yet.** This plan assigns the build.

> **Decisions locked (2026-06-26).** M1 contracts **frozen** (PI sign-off). **Solo software**
> build — ThS. Phó Trí Tín owns fusion + HMI + simulator. Hardware **procurement kicks off at
> S0**, but firmware *development* is best-effort (a student / G4) and **never gates the
> software**. This revision re-sequences the sprints for a single developer.

Companion specs: requirements [`02`](02-requirements.md), architecture [`03`](03-architecture.md),
protocol [`04`](04-message-protocol.md), warning logic [`05`](05-warning-logic.md),
HMI [`06`](06-hmi-design.md), simulator [`08`](08-simulation.md), evaluation [`11`](11-evaluation-plan.md).

## 16.1 Owners

| Code | Role | People | Owns |
|------|------|--------|------|
| **D** | Software (you) | 1 (solo) | fusion engine + HMI + simulator + contracts + logging + eval tools |
| **W** | Firmware / HW liaison | student · best-effort | ESP32 sensor nodes to the frozen contract (non-gating → G4) |
| **R** | Research / eval | PI + students | scenarios S1–S6, expert/driver review, report |

**D is a serial critical path** — one person, so fusion, HMI, and the simulator are built in
sequence, not in parallel. Two consequences shape everything below:
- **R is the real parallel relief.** PI + students formalize the S1–S6 scripts (feeding S4/S5)
  and run the G5 review prep, so D is not also doing scenario design and recruiting.
- **W never gates D.** Sim/real parity means the whole software stack is demoable with **no
  hardware** through M3. If a student delivers ESP32 firmware against the frozen contract, it
  plugs in at G4; if not, the simulator carries the demo. Hardware is *procured* at S0 so it is
  on the shelf when firmware work happens — buy early, develop later.

## 16.2 Gate (DONE): M1 freeze

- [x] **PI sign-off — contracts frozen** (2026-06-26). `schemas/` + [`04`](04-message-protocol.md)
  are locked; changes now need a major version bump + an ADR.
- [ ] `git init` + `.gitignore`; commit the doc set; tag `m1-contracts-frozen`. *(First task of S0.)*

## 16.3 Sprint plan (solo, ≈2-week sprints; S0 from end of G2, S1–S6 across months 5–7)

| Sprint | Goal | Milestone / exit |
|--------|------|------------------|
| **S0** Foundation | repo, dev env, executable contract | `docker compose up` → broker; **L1** green in CI; hardware ordered |
| **S1** Vertical slice | one zone end-to-end | scripted sim → fusion → HMI: RIGHT turns red in-browser |
| **S2** Fusion core | all severity / debounce / context logic | **L2** unit tests green |
| **S3** HMI build-out | all 8 zones, audio, liveness | full HMI demoable; UNKNOWN / SIGNAL-LOST works |
| **S4** Sim + scenario runner | geometric sim + S1–S6 replay | **L3** scenario suite runs in CI |
| **S5** → **M3** ✅ | consolidate + first review | ⭐ **M3 reached**: S1–S6 green end-to-end; pipeline demoable; logs reproducible ([`18`](18-m3-summary.md)) |
| **S6** Tune + demo | tune defaults, demo build, buffer | **operating point data-justified** ([`19`](19-tuning-and-operating-point.md)); demo polish deferred (cosmetic) |

### S0 — Foundation
- Scaffold the [`03 §3.7`](03-architecture.md) layout; `git init` + tag; `deploy/docker-compose.yml`
  (Mosquitto + **WebSocket listener**, ADR-0002 #1); CI = **L1 contract tests** (validate one
  fixture per message type + both configs vs `schemas/` — promote the round-2 validation script)
  + add the fixtures; TS skeletons for `apps/hmi` + `apps/simulator` with an MQTT-WS client
  connected to the broker.
- **Order hardware now** (ESP32 ×4, HC-SR04 ×8, 7" display) — long lead; on the shelf for W / G4.
- **R (parallel):** lock S1–S6 as data (placements, vehicle context, expected timeline).
- **Exit:** `docker compose up` runs the broker; CI green; a CLI publisher validates on `bsw/sensor/#`.

### S1 — Vertical slice (retire integration risk)
- `fusion-engine` MVP (load configs, reverse index, one-zone severity, retained `bsw/zone`,
  `bsw/health/fusion` heartbeat — ADR-0006 #2); scripted sim publisher (`bsw/sensor/right_mid`);
  HMI MVP (subscribe, draw truck + RIGHT zone from `zones.json`, tint by severity).
- **Exit:** scripted object → RIGHT SAFE→CAUTION→DANGER in the browser, end-to-end. From here
  everything is "thicken a component," not "will it integrate."

### S2 — Fusion core (FR-04/08/09/14, NFR-04, ADR-0007/0008)
- Full severity over all zones (empty-present ⇒ SAFE, [`05 §5.2`](05-warning-logic.md)); confirm/
  release + asymmetric distance hysteresis; **confirm-by-range** (`immediate_danger_factor`);
  multi-sensor precedence; **context modifiers** ([`05 §5.4`](05-warning-logic.md)); **stale-debounce
  + local-arrival staleness** (ADR-0008 #1) → UNKNOWN; JSONL + SQLite logging (FR-10); **L2 unit
  tests** (table-driven, driven by synthetic readings from the S1 publisher).
- **Exit:** L2 green; fusion feature-complete vs `05`; a dropped sensor → UNKNOWN (never SAFE).

### S3 — HMI build-out (FR-05/06/07/12/15, NFR-08/12, ADR-0006)
- All 8 zones from `zones.json` (polygons, centroids); object icons (generic blob, phase-1);
  primary-alert banner; distance readout; **Web Audio engine** (beeps + rate-limited fault chime,
  [`05 §5.5`](05-warning-logic.md)); **liveness clock + "alive" pip + "warming up" + "SIGNAL
  LOST"** (ADR-0006 #3, local-receipt per ADR-0008 #2); settings + diagnostics views (FR-12 / NFR-11).
- **Exit:** full HMI demoable from the scripted sim; **kill fusion → map UNKNOWN** within the
  freshness window (TC-F4).

### S4 — Simulator + scenario runner (FR-13, L3, the proposal deliverable)
- **Geometric sim:** object placement → sensor-cone test → realistic `bsw.sensor_reading` with
  optional noise / dropout ([`08 §8.2–8.3`](08-simulation.md)); vehicle-context controls.
- **Python scenario runner** (`tools/`) replaying S1–S6 deterministically → **L3 regression
  suite** in CI; `tools/` log-replay + **single-observer latency tool** (ADR-0008 #3).
- *(The interactive drag-drop web scene-editor is a stretch — see §16.7. The scripted runner is
  the M3-critical artifact and the lighter build for a solo dev.)*
- **Exit:** L3 suite runs S1–S6 in CI.

### S5 — Consolidate → M3 ⭐ ✅ (done)
- [x] Wire everything end-to-end; close gaps; TC-S1…S6 + TC-F1…F3, F5 green in CI.
- [x] **End-to-end over the broker**, proven two ways: a broker-free in-process **integration
  shim** (real `FusionService` + real wire stream over a loopback bus → asserts the live path
  matches the in-process L3 outcomes; deterministic, every-push CI) and a **broker-backed test**
  (real paho+TCP, runs in the compose CI job / a local `docker compose up`).
- [x] **One-command bring-up:** `docker compose up` → broker + fusion; `--profile hmi` serves the
  built HMI. Dockerfiles for both; `config/` + `logs/` mounted. Run book: [`17`](17-demo-and-run.md).
- [x] **HMI↔fusion command loop:** fusion honors `bsw/cmd` (`set_threshold` / `enable_zone` /
  `disable_zone` / `reload_config`); L2 tested. (The S6 tuning lever.)
- [x] **Reproducible logs** (11 §11.6): identical scenario → byte-identical `events.jsonl` +
  identical replayed metrics (regression-tested).
- [x] **Indicative latency:** `latency_observer` (live) + `scenario_runner --latency` (sim);
  headline stays L4 bench.
- **CI approach (decided):** two jobs — `tests` (L1/L2/L3 + integration shim + reproducibility; no
  broker, deterministic) and `integration` (brings up the shipped compose stack and runs the
  broker-backed test with `BSW_REQUIRE_BROKER=1` so a broken stack fails the job). The shim gives
  live-path coverage without infra; the compose job validates the actual deliverable.
- **R:** first informal glance review of the HMI; validate scenario expected-outcomes.
- **Exit:** **M3 reached** — full pipeline runs all scenarios in sim, demoable (incl. boot
  warming-up + TC-F4 kill→SIGNAL-LOST); logs replay reproducibly. Summary: [`18`](18-m3-summary.md).

### S6 — Tune + demo + buffer (NFR-09) — in progress
- [x] **Operating point chosen + justified with data.** `tools/threshold_sweep.py` sweeps the
  debounce levers (confirm/release/margin/immediate_danger_factor) over detection (latency) vs
  nuisance (noise-induced false-DANGER) scenarios; judged against NFR-01 with the real-path latency
  the sim omits. Result: the **current defaults are validated at the knee** (`confirm=3` breaks the
  latency budget once the physical path is added; `confirm=1` is too noisy). No config change; suite
  unchanged. Per-zone thresholds remain live-tunable via `bsw/cmd/set_threshold` (S5). Write-up:
  [`19-tuning-and-operating-point.md`](19-tuning-and-operating-point.md). **Re-run at L4** with real
  noise stats to confirm/refine.
- [x] **Day/night/auto HMI theme** (cosmetic polish) — high-contrast daylight + dark night mode,
  Settings → Theme, persisted, auto-by-time-of-day; severity semantics + color-blind-safe channels
  unchanged across themes. tsc/build/16 tests green; both themes visually verified.
- [ ] Demo build packaging — **deferred (cut-first cosmetic, §16.7)**; not needed for the milestone.
- **W:** if a student has ESP32 group-fire firmware on the bench, begin the G4 hand-off.
- **Exit:** tuned defaults ✅ (data-justified); demo build (cosmetic, pending); green light for G4
  (real sensors → same HMI — parity already proven through M3).

## 16.4 Parallel tracks

**Research / R (PI + students) — the real relief for a solo dev.**
- Formalize S1–S6 scripts + expected outcomes (S0) → feed the runner (S4 / S5).
- Recruit ≥ 5 drivers + ≥ 2 experts; finalize the glance-test + Likert protocol
  ([`11 §11.5`](11-evaluation-plan.md)) for **G5**.
- Own the eval-report skeleton; enforce **L4-bench** (not L3-sim) headline metrics
  ([`14 §P2`](14-architecture-critique.md) #6 / [`15`](15-architecture-critique-round2.md) R2-8).

**Firmware / W (student · best-effort · non-gating).**
- ESP32 + HC-SR04 → `bsw.sensor_reading`; **group-fire** (ADR-0007 #1, `fire_group`); optional
  SNTP (ADR-0008 #4); Wi-Fi → broker, UART/RS-485 fallback ready (ADR-0002 note).
- Hardware **procured at S0**; firmware developed whenever the student is available; plugs into
  **G4** with no downstream change. **The software path to M3 does not depend on it.**

## 16.5 Open ADR/spec action items → tasks

| Action item | Sprint | Owner |
|-------------|--------|-------|
| ADR-0002 #1 — Mosquitto WebSocket listener | S0 | D |
| ADR-0006 #2 — fusion heartbeat + monotonic zone `ts` | S1 / S2 | D |
| ADR-0006 #3 — HMI liveness clock + pip + warm-up | S3 | D |
| ADR-0006 #1 — Pi hardware watchdog | G4 (Pi image) | W |
| ADR-0007 #2 — confirm-by-range (param already in config) | S2 | D |
| ADR-0007 #1 — `fire_group` firmware schedule | W track | W |
| ADR-0008 #1 — local-arrival staleness (fusion) | S2 | D |
| ADR-0008 #2 — HMI freshness from local receipt | S3 | D |
| ADR-0008 #3 — single-observer latency tool | S4 | D |
| ADR-0008 #4 — ESP32 SNTP (optional aid) | W track | W |

## 16.6 Critical path, risks, Definition of Done

**Critical path (fully serial on D):** M1 freeze → S0 broker + CI → S1 slice → S2 fusion →
S3 HMI → S4 runner → **S5 M3**. R runs alongside (scenario scripts, eval prep); W is best-effort
and never blocks D.

**Risks (solo-weighted):**
- *Single point of failure (D).* No parallelism to absorb slippage → **S6 is an explicit buffer**,
  and §16.7 lists the scope cuts that protect M3.
- *Sensor procurement / quality.* Parity keeps S0–S5 unblocked; hardware is ordered at S0.
- *Vehicle-signal access.* Context degrades to "monitor all zones"; the sim supplies signals to M3.
- *Scope creep into AI.* Camera / VRU stays phase-2 — explicitly out of this plan.

**Definition of Done (each component):** honors the frozen schemas (L1); has tests at its level
(fusion → L2, scenarios → L3); runs under `docker compose up`; claims **no** `object_class`-dependent
behavior for phase-1.

**M3 exit:** S1–S6 + the fault cases run end-to-end in sim, green in CI; the HMI is demoable; logs
replay reproducibly; defaults are tuned to a credible operating point. M3 de-risks the rest — demo
and feedback proceed even if hardware slips.

## 16.7 Solo execution notes

One developer on the G3 bulk is **ambitious but tractable**: the design is fully specified
(docs 01–15) and the contract is frozen, so most of the hard thinking is done — S2–S5 are
implementation against an unambiguous spec, not open design. To protect M3, build in this
priority order and cut from the bottom if time is tight.

**Must (the M3 core):** fusion core (S2) · all-8-zone HMI + audio + liveness (S3) · Python
scenario runner / L3 suite (S4) · the scripted S1–S6 demo (S5).

**Cut / defer first under time pressure:**
1. Interactive drag-drop web **scene-editor** → use the Python scripted runner for demos.
2. **Settings / calibration UI** (FR-12, "Could") → tune via `bsw/cmd` from a CLI instead.
3. **Diagnostics view** polish → keep a minimal raw-message log.
4. Day/night theming, animations → cosmetic.

**Keep ruthlessly:** the fail-loud paths (UNKNOWN, liveness, SIGNAL-LOST) and the scenario
runner — they are the evaluation evidence (Nội dung 6) and the safety story, not polish.
