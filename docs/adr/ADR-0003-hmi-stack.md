# ADR-0003: Web stack for the in-cabin HMI

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** Software team

## Context
The HMI must render an animated top-view of the truck with color-coded zones and object
icons at ≥10 Hz, play audio alerts, run full-screen in the cabin, and also be easy to demo
to professors and companies and reuse as project infographics. It runs on the Pi but should
also run on a developer laptop during simulation.

## Decision
Build the HMI as a **web application: React + TypeScript**, rendering the scene on an
**HTML5 Canvas** (SVG acceptable for static parts), audio via the **Web Audio API**, served
locally and displayed in **Chromium kiosk** mode on the Pi. It subscribes to zone state via
**MQTT-over-WebSocket**.

## Options Considered

### Option A: Web (React + TS + Canvas) (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low–Med |
| Cost | Free |
| Portability | Runs on Pi, laptop, tablet, phone — anywhere with a browser |
| Team familiarity | High; very teachable |

**Pros:** Maximum portability and demo reach; Canvas handles smooth ≥10 Hz redraws; Web
Audio needs no sound assets; shares rendering code with the web simulator; trivially
becomes screenshots/infographics for the report.
**Cons:** Browser kiosk to manage; not a "native automotive" look (fine for a prototype).

### Option B: Native desktop (Qt or Flutter)
**Pros:** Native performance; single binary.
**Cons:** Steeper learning curve; less portable for demos; no code reuse with a web
simulator; heavier toolchain for students.

### Option C: Microcontroller GUI (LVGL on a TFT)
**Pros:** No Pi needed; low power.
**Cons:** Tied to Option B of [ADR-0001](ADR-0001-edge-compute-platform.md) (rejected);
crude graphics; hard to demo and to iterate; no AI/rich UI path.

## Trade-off Analysis
The web stack uniquely lets the **same canvas code** power both the HMI and the simulator,
runs on the chosen Pi *and* on any laptop for development, and produces presentation-ready
visuals for the academic deliverables — all with the stack students most readily learn.

## Consequences
- **Easier:** dev anywhere; shared sim/HMI rendering; instant demos; report visuals.
- **Harder:** manage Chromium kiosk autostart and GPU/perf on the Pi; ensure offline/local
  operation (no internet dependency).
- **Revisit when:** a productized in-dash unit needs a native/automotive UI or certification.

## Action Items
1. [ ] Scaffold React+TS app with a Canvas scene component (truck + zones from config).
2. [ ] MQTT-WS client; render on retained `bsw/zone/#`; UNKNOWN-on-stall behavior.
3. [ ] Web Audio alert engine (CAUTION/DANGER/fault tones).
4. [ ] Chromium `--kiosk` autostart unit on the Pi; day/night theme.
