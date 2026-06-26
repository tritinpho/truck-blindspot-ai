# 02 — Requirements

Requirements are identified so they can be traced to design, tests, and the evaluation
report (proposal Nội dung 6 — *đánh giá tính khả thi*). Priority uses MoSCoW:
**M**ust / **S**hould / **C**ould / **W**on't-this-phase.

## 2.1 Functional requirements

| ID | Priority | Requirement |
|----|----------|-------------|
| FR-01 | M | The system shall monitor a configurable set of blind-spot zones around the truck (default: `FRONT`, `FRONT_LEFT`, `FRONT_RIGHT`, `LEFT`, `RIGHT`, `REAR_LEFT`, `REAR_RIGHT`, `REAR`). |
| FR-02 | M | Each sensor shall carry a **position code** that the fusion engine maps to exactly one zone via configuration ([`config/sensors.example.json`](../config/sensors.example.json)). |
| FR-03 | M | The number and position of sensors shall be reconfigurable **without code changes** (modularity is the proposal's core novelty). |
| FR-04 | M | The fusion engine shall classify each zone into a severity: `SAFE`, `CAUTION`, or `DANGER`, based on detected range / presence and configurable thresholds. |
| FR-05 | M | The HMI shall render a **top-view** diagram of the truck and color each zone by its current severity (e.g. grey/green = safe, amber = caution, red = danger). |
| FR-06 | M | The HMI shall display an **icon** of the detected object in the zone's location. *(Phase 1: a generic blob at zone granularity. Class-specific icons and VRU threshold weighting depend on `object_class`, produced only by the **phase-2 camera** — see the phase note below.)* |
| FR-07 | M | The system shall emit an **audible alert** that escalates with severity (e.g. silent → slow beep → fast/continuous beep). |
| FR-08 | S | Warning logic shall be **context-aware**: turn-signal, reverse gear, and speed inputs adjust which zones alert and how aggressively, to reduce alert fatigue (see [`05-warning-logic.md`](05-warning-logic.md)). |
| FR-09 | S | The system shall apply **debounce / hysteresis** so transient detections do not cause flicker or chattering alarms. |
| FR-10 | S | The system shall **log** detection and alert events with timestamps for later evaluation (black-box / feasibility evidence). |
| FR-11 | C | A camera-based detector shall **classify** objects (pedestrian / cyclist / motorbike / vehicle) in at least the highest-risk zone (right / front-right). |
| FR-12 | C | The HMI shall expose a **settings / calibration** view (thresholds, zone enable/disable, volume). |
| FR-13 | M | A **simulator** shall be able to drive the entire pipeline by publishing synthetic sensor data on the same contracts as real sensors (FR-02). |
| FR-14 | S | The system shall surface a **sensor health / fault** indication (e.g. a stuck or disconnected sensor is shown as `UNKNOWN`, not silently `SAFE`). |
| FR-15 | M | The system shall continuously indicate its own **liveness**. If the fusion/zone stream stalls — a component crash *or a whole-Pi freeze* — the HMI shall degrade the entire map to `UNKNOWN` with a "signal lost" banner within a freshness window, and show an always-animating "alive" pip, so a frozen screen is never mistaken for "all clear". ([ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)) |

> **Phase-1 vs phase-2 (class-dependent behavior).** Every `object_class`-dependent feature —
> class-specific icons (FR-06), VRU threshold weighting (FR-11; [05 §5.2](05-warning-logic.md)),
> and object class in the event log — is **phase-2 (camera)**. The phase-1 ultrasonic system
> detects presence/range only and renders a generic blob with uniform thresholds. The
> evaluation plan must not report VRU-weighting or classification results from L3 sim as
> delivered phase-1 capability ([14 §P2](14-architecture-critique.md) #7).

## 2.2 Non-functional requirements

| ID | Priority | Requirement | Target |
|----|----------|-------------|--------|
| NFR-01 (Latency) | M | End-to-end latency, object-in-zone → visible/audible warning, **split by path** ([ADR-0007](adr/ADR-0007-sensor-firing-schedule.md)): *danger-path* (range well inside `danger_m`, immediate `confirm=1` escalate) vs *boundary-path* (near threshold, needs `confirm=2`). | **danger-path ≤ 200 ms** (stretch ≤ 150 ms); boundary-path ≤ ~250 ms (one extra sample period) |
| NFR-02 (Refresh) | M | HMI redraw, and sensor sampling rate **per modality** (ultrasonic uses group-fire to avoid cross-talk, [ADR-0007](adr/ADR-0007-sensor-firing-schedule.md)). | HMI **≥ 10 Hz**; ultrasonic **~5 Hz/sensor** (≥10 Hz master ÷ 2 non-adjacent groups); radar/camera **≥ 10 Hz** |
| NFR-03 (Availability) | S | Start automatically on power-up; recover from a component crash; a **hardware watchdog** reboots a wedged kernel/userspace ([ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)). | Auto-restart < 5 s; watchdog reboot on hang |
| NFR-04 (Fail-safe) | M | A failed/disconnected sensor or lost message stream shall be **visibly indicated**, never shown as "safe". | FR-14 enforced |
| NFR-05 (Cost) | M | Prototype BOM shall fit the project budget. | Software: open-source only |
| NFR-06 (Portability) | S | Fusion engine and HMI shall run on a Raspberry Pi-class device **and** on a developer laptop (for simulation). | Linux + Win/macOS dev |
| NFR-07 (Configurability) | M | Zone map, sensor map, and thresholds are external config, hot-reloadable where practical. | JSON config, no rebuild |
| NFR-08 (Usability) | M | Driver must understand the warning location within a single glance (~1 s). | Validated with expert/driver review (Nội dung 6) |
| NFR-09 (Alert quality) | S | False-positive rate low enough that drivers keep the system on. | Tuned via thresholds + context logic; measured in eval |
| NFR-10 (Maintainability) | S | Components are decoupled via the message bus; each is independently testable/replaceable. | Contract-first design |
| NFR-11 (Observability) | C | Operators can inspect live message flow and logs for debugging and demos. | MQTT topics + structured logs |
| NFR-12 (Startup) | S | The system shall show an explicit "warming up — not yet monitoring" state from power-on until the first healthy zone snapshot, so the pull-away maneuver (S1) is never silently unprotected. | Boot-to-monitoring state shown; target < 40 s ([ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md)) |

## 2.3 Operational scenarios (the system must behave well in)

Derived from the proposal's listed situations (*xuất phát, rẽ, chuyển làn, lùi, dừng đỗ,
lưu thông đô thị*):

- **S1 Pull-away** from a stop with a motorbike in `FRONT` / `FRONT_RIGHT`.
- **S2 Right turn** (highest risk) — motorbike squeezing along `RIGHT` / `FRONT_RIGHT`.
- **S3 Left turn / lane change** — vehicle in `LEFT` / `REAR_LEFT`.
- **S4 Reversing** — object in `REAR` / `REAR_LEFT` / `REAR_RIGHT`.
- **S5 Crawling in dense urban traffic** — multiple zones occupied; avoid alarm overload.
- **S6 Parked / stationary near a wall or guardrail** — must not nag with constant DANGER.

Each scenario maps to test cases and to context-aware rules in [`05-warning-logic.md`](05-warning-logic.md).

## 2.4 Assumptions & dependencies

- A 12 V (or bench 5 V) power source is available; power design is the hardware track's job.
- Vehicle signals (turn indicators, reverse, speed) **may** be available via direct wiring
  or OBD-II/CAN. Where unavailable, context-aware features (FR-08) degrade gracefully to
  "always monitor all zones".
- The display is a small dashboard screen (HDMI/touch) or a tablet; the HMI is resolution-adaptive.
