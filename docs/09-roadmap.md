# 09 — Roadmap (12 months, software view)

Mapped to the proposal's six phases (Nội dung 1–6 / Giai đoạn 1–6). Phase durations match
the proposal; the **software** deliverables per phase are spelled out here. Thanks to
sim/real parity, most software is built and validated before hardware exists.

| Phase | Months | Proposal focus | Software deliverables |
|-------|--------|----------------|-----------------------|
| **G1** | 1–2 | Survey blind spots, hazard situations, requirements | Finalize [`02-requirements.md`](02-requirements.md); zone model + scenarios S1–S6; freeze message contracts ([`04`](04-message-protocol.md), [`schemas/`](../schemas/)). |
| **G2** | 3–4 | Design sensor layout, zones, system schematic | [`config/zones`](../config/zones.example.json) + [`sensors`](../config/sensors.example.json) for target truck types; architecture baselined ([`03`](03-architecture.md)); broker + skeleton services stood up. |
| **G3** | 5–7 | Signal-processing logic, sensor→zone mapping, HMI | **Fusion engine** (severity, debounce, context) + **HMI** (top-view, audio) + **simulator**, all running against simulation. This is the bulk of the software build. |
| **G4** | 8–10 | Build simulation / small-scale physical model | Bring up ESP32 nodes against the frozen contract; integrate real readings (only the producer changes). Optional camera-AI VRU classification on the right zone (FR-11). |
| **G5** | 11 | Test, evaluate, expert/driver review, refine | Scenario regression suite; tune thresholds (NFR-09); glance-test (NFR-08); collect logs (FR-10) for the report. |
| **G6** | 12 | Final report, infographic, demo, next-step proposal | Demo build (sim + bench), evaluation report inputs, architecture diagrams as infographic, packaging for handoff. |

## Milestones

- **M1 (end G1):** Contracts + requirements frozen. Any component can be built independently.
- **M2 (end G2):** Configs + architecture baselined; dev stack runs via Docker Compose.
- **M3 (end G3):** Full pipeline works in simulation end-to-end (the demo-able core). ⭐
- **M4 (end G4):** Bench model with real sensors driving the same HMI.
- **M5 (end G5):** Tuned, evaluated, evidence collected.
- **M6 (end G6):** Final deliverables + follow-on (cấp sở / enterprise) proposal package.

## Critical path & risks

- **M3 is the linchpin** — a working simulated system de-risks everything: it lets the team
  demo, gather feedback, and proceed even if hardware procurement slips.
- **Risk: sensor procurement/quality.** Mitigation: parity means software is unblocked;
  start with cheap ultrasonic, keep a radar upgrade path ([ADR-0004](adr/ADR-0004-sensor-modality.md)).
- **Risk: vehicle-signal access** for context logic. Mitigation: features degrade gracefully
  to "monitor all zones"; signals can be simulated/wired on the bench.
- **Risk: scope creep into AI.** Mitigation: camera AI is explicitly **phase 2 / Could**
  (FR-11); the core (ultrasonic + zones + HMI) stands alone.

## Suggested team split

- **Software-fusion** (1–2): fusion engine, contracts, logging, eval tools.
- **Software-HMI** (1): HMI + simulator (shared canvas code).
- **Firmware/HW liaison** (1): ESP32 nodes to contract; mounting with HW track.
- **Research/eval** (PI + students): scenarios, expert review, report.
