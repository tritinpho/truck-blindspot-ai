# apps/hmi — in-cabin HMI (vanilla TS + Canvas + Web Audio, Chromium kiosk)

The driver-facing screen: a config-driven top-view of the truck with color-coded zones, object
icons, escalating audio, and a fail-loud liveness indicator. Subscribes to retained `bsw/zone/#`
over MQTT-WebSocket and is **driven only by the broker**. Spec:
[06-hmi-design.md](../../docs/06-hmi-design.md); stack rationale
[ADR-0003](../../docs/adr/ADR-0003-hmi-stack.md) as refined by
[ADR-0009](../../docs/adr/ADR-0009-hmi-framework-vanilla-ts.md) (vanilla TS, no React — the scene
is an imperative ≥10 Hz Canvas loop; a framework would serve only the cut-first settings views).

**Status:** S3 — full HMI. All 8 zones + icons + primary-alert banner + range readouts, Web Audio
alerts, the liveness clock (warming-up / SIGNAL-LOST / alive pip), and the Settings + Diagnostics
views. Phase-1 renders a **generic blob** for every object (class-specific icons are phase-2/camera).

## Run

```bash
npm install
npm run dev          # http://localhost:5173
```

Bring the pipeline up so the HMI has data (separate terminals, repo root):

```bash
docker compose -f deploy/docker-compose.yml up -d     # Mosquitto (MQTT :1883, WS :9001)
(cd services/fusion-engine && python -m fusion)        # publishes bsw/zone/# + bsw/health/fusion
python tools/sim_demo.py                               # scripted multi-zone demo timeline
```

Broker override: `VITE_BROKER_WS=ws://<host>:9001`.

## Demo / acceptance walk-through (the S3 exit criteria)

- **Warming-up (NFR-12):** start the HMI **before** the fusion engine → "warming up — not yet
  monitoring" until the first zone snapshot arrives.
- **Full demo:** with fusion + `sim_demo.py` running, watch zones tint, the object blob + range
  appear at each zone centroid, the bottom banner follow the worst `risk_weight × severity`, and
  the audio escalate (slow beep → fast beep); the right-turn phase boosts the RIGHT side, the
  reverse phase boosts REAR, and the park phase shows LEFT visually with **audio suppressed**
  (standby). Click anywhere once to unlock browser audio.
- **SIGNAL-LOST (TC-F4):** `Ctrl-C` the fusion process → within the ~1 s freshness window the whole
  map goes UNKNOWN (hatched), a red "SIGNAL LOST" banner shows, and the **alive pip stops
  animating**. It recovers to live when fusion restarts.
- **Settings (FR-12):** the ⚙ button — per-zone Caution/Danger sliders (publish `bsw/cmd/fusion`
  `set_threshold`), zone enable/disable, volume, VI/EN. *(Fusion honoring `set_threshold` live is
  the S6 tuning task; the HMI publishes the correct command today.)*
- **Diagnostics (NFR-11):** long-press the title or press `d` — per-zone state + the raw
  per-sensor feed (lazy-subscribed to `bsw/sensor/#` only while open). `Esc` / Back returns.

## Verify (no broker needed)

```bash
npm run typecheck    # tsc --noEmit
npm test             # node --test — 16 unit tests on the safety-critical pure logic
npm run build        # tsc + vite production bundle
```

`test/` covers the fail-loud core directly under Node (type-stripped, no DOM/bundler):
`liveness.ts` (warming-up → monitoring → SIGNAL-LOST, the freshness boundary, LWT-fault,
recovery) and `select.ts` (worst-zone banner by `risk_weight × severity`; single-worst audio;
standby/mute → silent).

## Architecture (vanilla TS modules, ADR-0009)

```
src/
  main.ts       entry — wires bus → store → rAF loop (liveness, audio, scene, chrome)
  config.ts     loads config/zones.example.json; derives centroids (FR-03, swap to re-skin)
  store.ts      central mutable AppState (the bus writes, the loop reads)
  bus.ts        MQTT-WS: subscribe bsw/zone/# + bsw/health/#; lazy bsw/sensor/#; publish bsw/cmd
  liveness.ts   PURE — local-receipt freshness clock → phase (ADR-0006/0008). Unit-tested.
  select.ts     PURE — worst-zone banner + audio policy (05 §5.5/§5.6). Unit-tested.
  audio.ts      Web Audio engine — CAUTION/DANGER beeps + rate-limited fault chime
  scene.ts      Canvas renderer — zones, blobs, range, truck, hatch/pulse (color-blind safe)
  ui.ts         DOM chrome + view router (status bar, banner, overlay, settings, diagnostics)
  theme.ts      severity palette + non-color redundant encodings (06 §6.2)
  i18n.ts       VI/EN strings (default Vietnamese)
  types.ts      wire + app types
```

**Clock discipline (ADR-0008):** freshness/liveness are measured from the **local receipt time**
of fusion messages (`performance.now()`), never from a message `ts` — a foreign, possibly pre-NTP
clock. This is why "kill the compute → UNKNOWN" is correct on the bench, not just in sim.
