# ADR-0001: Central compute platform

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** PI (Nguyễn Cảnh Tuấn), software lead (ThS. Phó Trí Tín)

## Context
The "bộ xử lý trung tâm" must ingest several sensors, run the fusion/warning logic, drive a
graphical HMI, optionally run camera AI, and boot reliably in a cabin — on a ~20M VND budget
with an academic team that should also *learn* from the platform.

## Decision
Use a **Raspberry Pi 4 (Linux)** as the central processor for the prototype. Keep **ESP32**
microcontrollers as distributed *sensor nodes* (not as the central brain).

## Options Considered

### Option A: Raspberry Pi 4 (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–Med (full Linux, standard tooling) |
| Cost | ~1.8M VND |
| Scalability | Runs broker + fusion + HMI + camera AI together |
| Team familiarity | High (Python, web, Linux are teachable) |

**Pros:** Enough power for camera AI; runs the web HMI in kiosk; easy debugging; massive
community; one device hosts the whole software stack.
**Cons:** Higher power draw than an MCU; needs graceful shutdown / good SD card; not
automotive-grade (acceptable for a prototype).

### Option B: Pure microcontroller (ESP32 only, no Pi)
| Dimension | Assessment |
|-----------|------------|
| Complexity | High (hand-rolled UI, no OS) |
| Cost | Lowest (~0.1–0.2M) |
| Scalability | No room for camera AI / rich HMI |
| Team familiarity | Medium |

**Pros:** Cheapest, lowest power, deterministic.
**Cons:** No practical camera AI; crude HMI; harder to demo and to teach modern stacks;
fights the project's AI/IoT learning goals.

### Option C: Industrial PC / Jetson Nano
**Pros:** More AI horsepower (Jetson).
**Cons:** Over budget / overkill for an 8-zone advisory display; longer procurement.

## Trade-off Analysis
The Pi hits the sweet spot: cheap enough for the budget, powerful enough for the AI
*stretch* goal, and the friendliest platform for students to build and demo a complete
system. ESP32s still earn their place as cheap, distributable sensor nodes near each sensor.

## Consequences
- **Easier:** one device runs broker+fusion+HMI(+AI); rich, demoable, teachable stack.
- **Harder:** must handle power/shutdown and SD reliability; not ruggedized (fine for proto).
- **Revisit when:** moving to a vehicle pilot → consider an automotive-grade compute module
  and CAN transport (see [ADR-0002](ADR-0002-message-bus.md) and [`../10-improvements.md`](../10-improvements.md) #14).

## Action Items
1. [ ] Procure Pi 4 + reliable PSU + quality SD (or boot from SSD).
2. [ ] Base image with Mosquitto, Python, Chromium-kiosk, systemd units.
3. [ ] Document graceful-shutdown handling for in-cabin power-down.
