# 07 — Technology Stack & Rationale

Chosen to fit a **~20M VND budget**, a **12-month academic timeline**, an **IoT/AI/embedded
learning goal**, and the need to **demo without hardware**. Everything software is
open-source. Detailed trade-offs are in the ADRs ([`adr/`](adr/)).

## 7.1 At a glance

| Layer | Choice | Why (short) |
|-------|--------|-------------|
| Central compute | **Raspberry Pi 4** (Linux) | Cheap, runs full stack + camera AI, easy student dev. [ADR-0001](adr/ADR-0001-edge-compute-platform.md) |
| Sensor nodes | **ESP32 + HC-SR04 ultrasonic** (proto); radar/IR upgrade path | Very low cost, Wi-Fi/UART/CAN capable, huge community. [ADR-0004](adr/ADR-0004-sensor-modality.md) |
| Message bus | **MQTT (Mosquitto)** | Lightweight pub/sub; MCU + browser friendly; enables sim/real parity. [ADR-0002](adr/ADR-0002-message-bus.md) |
| Fusion engine | **Python 3** (paho-mqtt) | Fast to write, ample for these data rates, great for students. |
| HMI | **Vanilla TypeScript + Vite + Canvas**, Chromium kiosk | Cross-platform, demoable anywhere, doubles as infographic. [ADR-0003](adr/ADR-0003-hmi-stack.md), [ADR-0009](adr/ADR-0009-hmi-framework-vanilla-ts.md) |
| Simulator | **Web (vanilla TS)** or **Python** producer | Same contracts as real sensors; the "computer simulation" deliverable. [ADR-0005](adr/ADR-0005-sim-real-parity.md) |
| Camera AI (phase 2) | **Pi Camera + TFLite/ONNX** (YOLO-nano / MobileNet-SSD) | On-device VRU classification at low cost. |
| Logging | **SQLite + JSONL** | Zero-config local black-box for the evaluation report. |
| Packaging/deploy | **Docker Compose** (dev) + **systemd** (Pi) | One-command dev; reliable boot on the Pi. |
| Vehicle signals | **GPIO** wiring or **OBD-II/ELM327** | Turn/reverse/speed for context-aware logic; optional. |

## 7.2 Languages

- **Python** — fusion engine, vehicle adapter, tools/eval scripts, optional simulator.
- **TypeScript/JavaScript** — HMI and web simulator.
- **C/C++ (Arduino/ESP-IDF)** — ESP32 sensor-node firmware (HW track, contract in [`04-message-protocol.md`](04-message-protocol.md)).

## 7.3 Indicative prototype BOM (hardware track — for context)

> Software is free; this shows the budget is realistic. Prices are rough VND, illustrative.

| Item | Qty | ~Unit | ~Total |
|------|-----|-------|--------|
| Raspberry Pi 4 (2–4 GB) + SD + PSU | 1 | 1,800,000 | 1,800,000 |
| ESP32 dev board | 4 | 120,000 | 480,000 |
| HC-SR04 ultrasonic (or RCWL radar) | 8 | 25,000 | 200,000 |
| 7" HDMI/touch display | 1 | 1,200,000 | 1,200,000 |
| Buzzer/speaker + amp | 1 | 100,000 | 100,000 |
| Pi Camera v2 (phase 2) | 1 | 600,000 | 600,000 |
| Model truck + mounts, wiring, misc | — | — | ~1,500,000 |
| **Subtotal** | | | **~5.9M** |

Comfortably within 20M, leaving room for a radar/camera upgrade, spares, and incidentals.
(Final BOM owned by the hardware track.)

## 7.4 Why not alternatives (one-liners; see ADRs for depth)

- **Pure microcontroller (no Pi):** cheaper, but no room for camera AI, harder for students,
  no easy web HMI. Rejected for the main compute; ESP32s remain as sensor nodes.
- **Cloud backend:** adds latency, connectivity dependence, and cost for a safety-adjacent,
  in-cabin, real-time job. Everything stays on-device.
- **Native desktop HMI (Qt/Flutter):** fine, but web maximizes portability and demo reach
  and lowers the student learning curve.
- **ROS 2:** powerful but heavy for an 8-zone advisory display on a tight budget/timeline.
  MQTT gives 90% of the decoupling at 10% of the complexity.

## 7.5 Dev environment

- Docker + Docker Compose to run broker + fusion + HMI + simulator on any laptop.
- Node.js LTS (HMI/sim), Python 3.11+ (services), PlatformIO/Arduino (firmware).
- Lint/format/test per language; contract tests validate messages against [`../schemas/`](../schemas/).
