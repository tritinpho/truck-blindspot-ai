# 06 — In-Cabin HMI Design

The HMI is what the driver actually experiences. Design goal (NFR-08): the driver
understands **where** the danger is in a **single ~1-second glance**, with eyes mostly on
the road. Icon-first, color-coded, minimal text.

## 6.1 Screen layout

```
┌─────────────────────────────────────────────┐
│  BSW                       ⚙   🔊  ●ok        │  status bar: title, settings, mute, health
├─────────────────────────────────────────────┤
│                   ▟ FRONT ▙                   │
│      ┌─────────────────────────────────┐      │
│  L   │            ███████              │  R   │  top-view truck, zones around it
│  E   │            █ CAB █              │  I   │
│  F   │            ███████              │  G   │
│  T   │            ███████              │  H   │
│      └─────────────────────────────────┘      │  zones tint by severity; icons appear
│                   ▟ REAR ▙                    │  at the detected location
├─────────────────────────────────────────────┤
│  ⚠ RIGHT — motorbike, 0.8 m                   │  primary-alert banner (worst zone)
└─────────────────────────────────────────────┘
```

The truck graphic is the proposal's "sơ đồ top-view của xe tải"; zones are the proposal's
"vùng cảnh báo".

## 6.2 Visual language

| Severity | Zone fill | Border | Motion |
|----------|-----------|--------|--------|
| SAFE | neutral dark / transparent | thin | none |
| CAUTION | amber, ~40% | amber | none |
| DANGER | red, ~70% | red | pulse / flash |
| UNKNOWN | grey hatched | dashed | none (one-shot fault chime) |

- **Color is never the only channel** (color-blind safe): severity also changes icon ring,
  border style, and motion. DANGER pulses; UNKNOWN is hatched.
- **Object icons** differ by class (pedestrian / cyclist / motorbike / vehicle / generic
  blob) using `object_class` — produced **only by the phase-2 camera**. **Phase 1 (ultrasonic)
  always renders the generic blob**; class-specific icons appear when a camera is added to a
  zone. Generic blob whenever class is unknown.
- Icons render at the **zone centroid**, not the object's exact sub-zone position: the
  `zone_state` contract carries severity + nearest range, not intra-zone coordinates — the
  8-zone model *is* the spatial resolution. The proposal's "biểu tượng tại vị trí tương ứng"
  is honored at zone granularity; finer placement would need a richer contract (deferred).
- **Distance** optionally shown as a small numeric next to the icon and/or proximity bars.

## 6.3 Sound (mirrors `05-warning-logic.md` §5.5)

- Web Audio API generates beeps (no asset files needed): slow beep = CAUTION, fast/
  continuous = DANGER, one-shot chime = new fault. Single worst severity sounds at a time.
- Mute button = timed silence; visual state never muted.

## 6.4 Modes / views

1. **Drive view** (default) — the layout above; full screen, kiosk, no chrome.
2. **Settings/Calibration** — sliders for `caution_m`/`danger_m` per zone, zone
   enable/disable, volume, language (VI/EN). Sends `bsw/cmd/...`. (FR-12)
3. **Diagnostics** (hidden/long-press) — live per-sensor readings, health, message rate;
   for bench testing and demos (NFR-11).

## 6.5 Technical rendering

- **Stack:** vanilla TypeScript ES modules (Vite, no framework — [ADR-0009](adr/ADR-0009-hmi-framework-vanilla-ts.md)); the truck/zone scene drawn on a single **HTML5 Canvas**
  layer for cheap, smooth ≥10 Hz redraws (NFR-02). Rationale: [ADR-0003](adr/ADR-0003-hmi-stack.md), refined by [ADR-0009](adr/ADR-0009-hmi-framework-vanilla-ts.md).
- **Data in:** subscribe to retained `bsw/zone/#` over MQTT-WebSocket; update on each message.
  Late join shows correct state instantly thanks to retained messages.
- **Responsive:** the scene scales to the screen (7" dashboard panel, tablet, or a laptop
  in dev). Layout adapts portrait/landscape.
- **Resilience & liveness ([ADR-0006](adr/ADR-0006-fail-loud-compute-liveness.md), FR-15):** the
  HMI runs a local **freshness clock** driven by the fusion heartbeat (`bsw/health/fusion`) and
  zone `ts`. If no fresh update arrives within the window (default 1 s) — broker/fusion down
  *or the whole Pi frozen* — the entire map degrades to UNKNOWN with a "SIGNAL LOST" banner,
  never a stale green. An always-animating **"alive" pip** (tied to the heartbeat) lets the
  driver tell "live, all clear" from "frozen on a green frame".
- **Startup (NFR-12):** on boot, a **"warming up — not yet monitoring"** screen shows until the
  first healthy zone snapshot, so the pull-away maneuver (S1) is never silently unprotected.
- **Kiosk:** Chromium in `--kiosk` autostarted on the Pi; full-screen, no cursor. A **hardware
  watchdog** reboots a wedged Pi (NFR-03 / ADR-0006).

## 6.6 Configurable truck silhouette

The truck outline and zone polygons come from [`../config/zones.example.json`](../config/zones.example.json)
so the same HMI renders a rigid truck, a tractor-trailer, or a bus by swapping config —
supporting the "different truck types / modular layout" goal (FR-03).

## 6.7 Accessibility & ergonomics

- High-contrast palette tuned for daytime glare and night dimming (auto day/night theme).
- Large hit targets for the few touch controls; primary info needs **no** interaction.
- Glance-test acceptance: in the expert/driver review (Nội bộ 6), drivers should locate the
  active zone correctly in ≤1 s in ≥95% of trials.
