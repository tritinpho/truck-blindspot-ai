# 01 — Project Overview & Context

## 1.1 Problem statement

Trucks, trailers, buses, and other large commercial vehicles have large **blind-spot
zones** (*điểm mù*) around the body — front, both sides, rear corners, and rear. Mirrors
and the driver's experience do not fully cover these zones. In Vietnamese urban traffic,
with high motorbike density and very small following distances, an undetected motorbike,
cyclist, or pedestrian in a blind spot is a leading cause of serious accidents — most
critically during **starting off, lane changes, turns, and reversing**.

Existing aids (mirrors, reversing cameras, multi-camera "around view") mostly give the
driver **more images to interpret**. The driver still has to find the danger and locate
it under time pressure — a cognitive-overload problem.

## 1.2 What we are building (the idea)

A system that:

1. **Detects** objects in each blind-spot zone using position-tagged sensors.
2. **Maps** every detection to a specific zone of a top-view truck diagram.
3. **Warns** the driver *spatially* — the right zone lights up on a display, with an
   icon and an escalating audible alert — so the danger's **location** is understood at
   a glance, not just its existence.

The novelty (per the proposal) is the **modular sensor-position → warning-zone mapping**:
sensors can be added/removed/repositioned per truck type, each carries a position code,
and the processor renders the matching zone. The software is built to make exactly this
configurable.

A framing note for the *tính mới* / patent angle: config-driven sensor→zone mapping is common
in commercial BSD / around-view units, so the more defensible differentiator is the
**context-aware anti-alert-fatigue logic** ([`05-warning-logic.md`](05-warning-logic.md) §5.4)
layered on top — turn-signal / reverse / speed steer *which* zones escalate and how hard. Worth
foregrounding for a cấp-sở or *giải pháp hữu ích* claim. See [`10-improvements.md`](10-improvements.md) #4
and [`14-architecture-critique.md`](14-architecture-critique.md) §P3.

## 1.3 Scope of *this* repository (software)

**In scope**

- Sensor-fusion / decision engine (detection → zone → severity).
- In-cabin HMI (top-view display, icons, color, audio).
- A pure-software simulator with sim/real parity.
- Message contracts (protocol + JSON schemas).
- Edge firmware *interface* and reference behavior for sensor nodes.

**Out of scope (hardware track, referenced but not built here)**

- Physical mounting/wiring of sensors, power, enclosure.
- PCB / electrical design.
- Vehicle integration and homologation.

The software is designed so the hardware track can proceed in parallel and plug in later.

## 1.4 Target deployments

| Stage | Form | Purpose |
|-------|------|---------|
| **A. Simulation** | PC / web simulator | Develop & demo logic and HMI with no hardware (proposal Nội dung 5, option 1) |
| **B. Bench model** | Model truck + ultrasonic sensors + Raspberry Pi + small screen | Small-scale physical proof of principle (proposal Nội dung 5, options 2–3) |
| **C. Vehicle pilot** | Real truck, ruggedized | Future — cấp sở / enterprise pilot |

The same fusion engine + HMI binaries serve A, B, and C; only the *input adapter* changes.

## 1.5 Stakeholders

| Role | Interest |
|------|----------|
| Principal investigators (Nguyễn Cảnh Tuấn; ThS. Phó Trí Tín) | Deliverables, feasibility evidence, follow-on funding |
| Faculty of Technology (PGS.TS Trần Đan Thư) | Academic rigor, teaching value |
| Students | Hands-on IoT/AI/embedded learning |
| Truck drivers | Usability, low false-alarm rate, trust |
| Transport / logistics firms | Retrofit cost, reliability, fleet value |
| Auto-equipment vendors | Productization, BOM, integration |

## 1.6 Glossary (EN / VI)

| Term | Vietnamese | Meaning |
|------|-----------|---------|
| Blind spot | Điểm mù | Area around the vehicle the driver cannot directly observe |
| Zone | Vùng cảnh báo | A named region of the top-view diagram (e.g. `RIGHT`, `FRONT_RIGHT`) |
| Sensor node | Cảm biến / nút cảm biến | A position-tagged detector reporting range/presence |
| Fusion engine | Bộ xử lý trung tâm | Service that turns detections into zone states |
| HMI | Giao diện người–máy | The in-cabin display + audio the driver perceives |
| Severity | Mức độ nguy hiểm | `SAFE` / `CAUTION` / `DANGER` state of a zone |
| VRU | Người tham gia giao thông dễ tổn thương | Vulnerable Road User: pedestrian, cyclist, motorbike |
| TTC | Thời gian đến va chạm | Time-to-collision estimate |
| Sim/real parity | Tương đương mô phỏng–thực | Same software runs on simulator and real hardware |
| Top-view | Sơ đồ nhìn từ trên | Bird's-eye schematic of the truck and its zones |

## 1.7 Driving constraints

- **Budget ~20M VND** → favor open-source software and low-cost, widely available
  hardware (Raspberry Pi, ESP32, HC-SR04 ultrasonic), see [`07-tech-stack.md`](07-tech-stack.md).
- **12 months, 6 phases, academic team** → simple, well-documented, demoable stack;
  contract-first so work parallelizes.
- **Right-hand traffic (Vietnam)** → the **right side & front-right** are the highest-risk
  zones (right-turn motorbike squeeze); the design weights these accordingly.
- **Safety-adjacent, not safety-certified** → BSW is a *driver assistance / advisory*
  aid, not an automatic intervention. This framing is stated explicitly to set
  expectations and limit liability. See [`10-improvements.md`](10-improvements.md).
