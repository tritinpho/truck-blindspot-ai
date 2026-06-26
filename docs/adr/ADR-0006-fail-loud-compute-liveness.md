# ADR-0006: Fail-loud on compute death — hardware watchdog + HMI liveness

**Status:** Accepted (ratified 2026-06-26)
**Date:** 2026-06-26
**Deciders:** PI (Nguyễn Cảnh Tuấn), software lead (ThS. Phó Trí Tín), hardware liaison

## Context
The architecture already fails *loud* when a **sensor** goes silent: its zone becomes
`UNKNOWN`, never a fake `SAFE` (FR-14 / NFR-04). But every software component — broker,
fusion engine, Chromium-kiosk HMI, logger — runs on a **single Raspberry Pi**
([ADR-0001](ADR-0001-edge-compute-platform.md)). If the Pi itself stalls (kernel lockup,
SD-card I/O wedge, GPU/Chromium hang, brown-out), the kiosk keeps displaying its **last
rendered frame** — possibly an all-green "safe" map — with nothing to contradict it. For an
advisory safety device, a frozen screen that *looks* safe is the worst failure mode: it
gives the driver false confidence at the exact moment the system is dead.

NFR-03 (auto-restart < 5 s via systemd) does not cover this: systemd cannot recover a kernel
or SD hang, and even a clean restart shows stale state during the boot window. Related: a
cold boot of Pi + Chromium kiosk is ~20–40 s, so the system may be **absent** during the
pull-away maneuver right after ignition (scenario S1) with no indication it is not yet ready.

This decision extends "fail loud, not silent" (03 §3.1) to the *compute platform itself*,
not just to sensors.

## Decision
Adopt a two-layer liveness defense plus an explicit startup state:

1. **Hardware watchdog.** Enable the Pi's on-board hardware watchdog (`/dev/watchdog`, e.g.
   systemd `RuntimeWatchdogSec`). A wedged kernel/userspace that stops petting the watchdog
   triggers an automatic reboot.
2. **End-to-end HMI liveness clock.** The fusion engine emits a ~1 Hz `bsw/health/fusion`
   heartbeat and a monotonic `ts` on every `bsw/zone/#`. The HMI runs a **local** timer: if
   no zone update / heartbeat arrives within a freshness window (default 1 s), the **entire
   map degrades to `UNKNOWN`** with a "SIGNAL LOST" banner — the existing stalled-stream
   behavior (06-hmi-design §6.5), now also driven by an explicit clock rather than only by
   message arrival. A small **always-animating "alive" pip**, tied to the heartbeat, lets the
   driver distinguish "system live, all clear" from "system frozen on a green frame."
3. **Startup state.** On boot the HMI shows an explicit **"warming up — not yet monitoring"**
   screen until the first healthy zone snapshot arrives, so S1 is never silently unprotected.

## Options Considered

### Option A: Hardware watchdog + HMI liveness pip (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low (watchdog is a config flag; the pip reuses the already-specified `bsw/health` heartbeat + UNKNOWN state) |
| Cost | Zero (on-board watchdog; no extra hardware) |
| Safety | Converts the dangerous "frozen-green" mode into the safe "UNKNOWN" mode the design already handles |
| Team familiarity | High |

**Pros:** Cheap; reuses existing contract elements (`bsw/health`, retained zone state,
`UNKNOWN`); directly closes the worst failure mode; demoable ("pull power → screen goes
UNKNOWN, not frozen-green").
**Cons:** A watchdog reboot still costs ~20–40 s; mitigated by the "warming up" screen and,
optionally, keeping the Pi on accessory power.

### Option B: External MCU supervisor + independent telltale lamp
A cheap ESP32 watches the Pi heartbeat over a wire and lights an **independent** red
"SYSTEM FAULT" lamp/buzzer if it stops.
**Pros:** Truly independent of the Pi; survives total Pi death including display power loss;
closest to an automotive telltale.
**Cons:** Extra hardware + wiring the HW track must own. **Recommended as the vehicle-pilot
upgrade**, not required for the bench prototype.

### Option C: Do nothing (rely on systemd auto-restart, NFR-03)
**Pros:** No work.
**Cons:** Leaves the frozen-green failure unaddressed; contradicts the project's own
"fail loud, not silent" principle.

## Trade-off Analysis
The project already renders `UNKNOWN` for dead sensors and stalled streams; the only gap is
that a *whole-platform* freeze has no trigger and no independent prod. Option A closes it for
~zero cost by reusing existing mechanisms. Option B is the right *pilot* hardening but is
hardware the cấp-trường bench does not need — defer it the way [ADR-0002](ADR-0002-message-bus.md)
/ [ADR-0004](ADR-0004-sensor-modality.md) defer CAN/radar.

## Consequences
- **Easier:** the most dangerous failure mode becomes the already-designed safe one; "kill
  the compute → UNKNOWN" is strong evaluation evidence (Nội dung 6).
- **Harder:** introduces a boot-time gap to manage (warming-up screen, accessory power);
  fusion must emit a dependable heartbeat and the HMI must run a liveness clock.
- **Revisit when:** vehicle pilot → add Option B (independent supervisor + telltale) and tie
  into vehicle power management.

## Action Items
1. [ ] Enable the Pi hardware watchdog in the base image (extends [ADR-0001](ADR-0001-edge-compute-platform.md) action #2); document reboot behavior.
2. [ ] Fusion: guarantee a ~1 Hz `bsw/health/fusion` heartbeat and a monotonic `ts` on every `bsw/zone/#`.
3. [ ] HMI: liveness clock → whole-map `UNKNOWN` + "SIGNAL LOST" on freshness timeout; add the always-animating "alive" pip; add the "warming up" startup screen ([06-hmi-design.md](../06-hmi-design.md) §6.5).
4. [ ] Requirements: add **FR-15** (system-liveness indication) and **NFR-12** (boot-to-monitoring budget + "not ready" indication) to [02-requirements.md](../02-requirements.md); add fault-injection **TC-F4** (freeze fusion / kill the Pi → expect map `UNKNOWN` within the freshness window) to [11-evaluation-plan.md](../11-evaluation-plan.md).
