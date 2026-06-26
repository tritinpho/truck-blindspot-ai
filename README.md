# Truck Blind-Spot Warning System (BSW)

> Working title: **BSW** — *Blind-Spot Warning*
> Vietnamese: *Hệ thống cảnh báo điểm mù cho xe tải*

A modular system that detects vehicles, pedestrians, and obstacles in the blind-spot
zones around a truck and warns the driver with a **visual top-view display** and
**audio alerts** inside the cabin. This repository holds the **software** side of the
project: the sensor-fusion engine, the in-cabin HMI, the simulator, and the message
contracts that tie them together.

This work is the software realization of the R&D proposal *"Nghiên cứu giải pháp cảnh
báo điểm mù cho xe tải để giảm thiểu tai nạn giao thông"* (HUTECH-style cấp trường
task, 12 months, ~20,000,000 VND).

---

## Why this exists

Large trucks have wide blind-spot zones at the front, both sides, and rear. In dense
Vietnamese traffic — where motorbikes ride very close to large vehicles — a driver
relying on mirrors alone cannot reliably see a motorbike or pedestrian in these zones.
The most lethal case is the **right-side / front-right squeeze during a right turn**.
BSW turns raw sensor detections into a *spatial, glanceable* warning so the driver
knows **where** the danger is, not just *that* there is one.

## What the software does

```
Sensors (or Simulator)  ──►  Sensor-Fusion Engine  ──►  In-cabin HMI (top-view + audio)
   ultrasonic/radar/          maps detection to a         color-coded zones, icons,
   camera, per zone           zone + severity, with       escalating beeps, context-
                              debounce & context logic     aware suppression
```

The same software runs against **real hardware** and against a **pure-software
simulator** without changes — both speak the same message protocol over a common bus.
This lets the team develop, demo, and evaluate the system even before the physical
model is finished. See [ADR-0005](docs/adr/ADR-0005-sim-real-parity.md).

## Repository map

| Path | What's inside |
|------|---------------|
| [`docs/01-overview.md`](docs/01-overview.md) | Context, glossary (EN/VI), stakeholders |
| [`docs/02-requirements.md`](docs/02-requirements.md) | Functional + non-functional requirements with IDs |
| [`docs/03-architecture.md`](docs/03-architecture.md) | System architecture, components, data flow, sequences |
| [`docs/04-message-protocol.md`](docs/04-message-protocol.md) | MQTT topics + JSON message contracts |
| [`docs/05-warning-logic.md`](docs/05-warning-logic.md) | Zone model, severity, debounce, context-aware rules |
| [`docs/06-hmi-design.md`](docs/06-hmi-design.md) | In-cabin display UX and rendering spec |
| [`docs/07-tech-stack.md`](docs/07-tech-stack.md) | Chosen technologies and rationale |
| [`docs/08-simulation.md`](docs/08-simulation.md) | The simulator and how sim/real parity works |
| [`docs/09-roadmap.md`](docs/09-roadmap.md) | 12-month plan mapped to the proposal's 6 phases |
| [`docs/10-improvements.md`](docs/10-improvements.md) | Suggested fixes & improvements to the proposal |
| [`docs/11-evaluation-plan.md`](docs/11-evaluation-plan.md) | Evaluation & test plan (feeds the feasibility report) |
| [`docs/12-traceability.md`](docs/12-traceability.md) | Proposal ↔ requirements ↔ design ↔ tests matrix |
| [`docs/13-privacy-ethics.md`](docs/13-privacy-ethics.md) | Privacy & ethics note (esp. the phase-2 camera) |
| [`docs/14-architecture-critique.md`](docs/14-architecture-critique.md) | Design-phase critique, round 1 + dispositions |
| [`docs/15-architecture-critique-round2.md`](docs/15-architecture-critique-round2.md) | Design-phase critique, round 2 (pre-implementation) |
| [`docs/16-build-plan.md`](docs/16-build-plan.md) | Sprint/task build plan (M1 → M3), mapped to the team split |
| [`docs/17-demo-and-run.md`](docs/17-demo-and-run.md) | Run book: one-command bring-up, the demos, reproducible logs, latency |
| [`docs/18-m3-summary.md`](docs/18-m3-summary.md) | M3 summary ⭐ — exit-criteria evidence, scenario coverage, CI approach |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records |
| [`config/`](config/) | Example zone & sensor configuration |
| [`schemas/`](schemas/) | JSON Schemas for the message contracts |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute (docs now; dev workflow when code lands) |
| [`LICENSE`](LICENSE) | Proprietary / all-rights-reserved (pending IP decision) |

## Quick orientation for new contributors

1. Read [`docs/01-overview.md`](docs/01-overview.md) then [`docs/03-architecture.md`](docs/03-architecture.md).
2. Skim the ADRs in [`docs/adr/`](docs/adr/) to understand *why* the stack is what it is.
3. The system is contract-first: the [`schemas/`](schemas/) and
   [`docs/04-message-protocol.md`](docs/04-message-protocol.md) are the source of truth.
   Any component (sensor node, fusion engine, HMI, simulator) can be built independently
   as long as it honors those contracts.

## Status

✅ **G3 complete — M3 reached** ([`docs/18-m3-summary.md`](docs/18-m3-summary.md)). The full
pipeline runs end-to-end in simulation: **broker → fusion → HMI**, driven by the scripted sim, with
S1–S6 + the fault cases green in CI, a one-command bring-up, the HMI↔fusion command loop, and
reproducible logs. Contracts are frozen at M1. Tuning the defaults to a credible operating point is
**S6**; real-sensor bring-up is **G4**. Build sequence: [`docs/16-build-plan.md`](docs/16-build-plan.md).

### Test (no hardware, no broker)

```bash
pip install -r tests/requirements.txt
pytest -q tests/ services/fusion-engine/tests        # L1 + L2 + L3 + integration shim + reproducibility
```

### Run the full pipeline (M3 demo)

```bash
# 1. broker + fusion in one command
docker compose -f deploy/docker-compose.yml up -d

# 2. drive a scenario over the broker (same wire messages a real rig emits)
python tools/scenario_runner.py S2 --live            # right-turn squeeze → RIGHT DANGER

# 3. open the HMI
docker compose -f deploy/docker-compose.yml --profile hmi up -d   # http://localhost:8080
# …or for hot reload:  cd apps/hmi && npm install && npm run dev   # http://localhost:5173
```

Kill fusion (`docker compose -f deploy/docker-compose.yml kill fusion`) to watch the map degrade to
**SIGNAL LOST** within ~1 s (TC-F4). Full run book + the fail-loud demos:
[`docs/17-demo-and-run.md`](docs/17-demo-and-run.md).
