# ADR-0009: HMI UI framework — vanilla TypeScript modules (refines ADR-0003)

**Status:** Accepted (ratified 2026-06-26)
**Date:** 2026-06-26
**Deciders:** Software lead (ThS. Phó Trí Tín)
**Refines:** [ADR-0003](ADR-0003-hmi-stack.md) (web stack for the in-cabin HMI)

## Context
[ADR-0003](ADR-0003-hmi-stack.md) chose a **web** HMI — *React + TypeScript*, scene on an
HTML5 **Canvas**, audio via **Web Audio**, served in a **Chromium kiosk**, subscribing over
**MQTT-WebSocket**. That decision was made on paper, before any code. The S1 vertical slice
then shipped the scene as **vanilla TS** (no React) and worked. S3 builds out the full HMI
(all 8 zones, icons, audio, liveness, settings, diagnostics), which forces the question the
build plan flagged: commit to React now, or keep vanilla? Every other ADR-0003 element
(TS, Canvas, Web Audio, MQTT-WS, kiosk) is unchanged and not in question — only the
**UI framework** is.

What the S1 slice and the S3 spec reveal about the actual shape of this HMI:

- The **safety-critical core is imperative**, not declarative. The drive view is a single
  `<canvas>` redrawn at ≥10 Hz (NFR-02) with *continuous* animation — the DANGER pulse and the
  always-animating "alive" pip ([ADR-0006](ADR-0006-fail-loud-compute-liveness.md)) run every
  frame. You draw this with `ctx.*` calls inside a `requestAnimationFrame` loop **regardless of
  framework**; React would wrap the canvas but never touch what's inside it. ~95% of the UI by
  importance lives here and gets *zero* benefit from a virtual DOM.
- The only parts a component framework genuinely helps — the **Settings** form and the
  **Diagnostics** table (FR-12 / NFR-11) — are exactly the two views the build plan marks as
  **cut-first under time pressure** ([16 §16.7](../16-build-plan.md)). We'd be adopting a
  framework to serve the lowest-priority, first-to-be-cut surface.
- This is a **single-screen kiosk appliance**, not a multi-route web app. There is no routing
  graph, no auth, no data-fetching cache, no SEO — the needs React is built to absorb.
- **Boot-to-monitoring is a requirement** (NFR-12, target < 40 s on a cold Pi + Chromium). A
  smaller bundle with no framework runtime is strictly better for the metric we're graded on.

## Decision
Build the S3 HMI as **vanilla TypeScript ES modules** — no React (no JSX/runtime/router). Keep
**every other ADR-0003 choice**: TypeScript, Canvas scene, Web Audio, MQTT-over-WebSocket,
Chromium-kiosk delivery, Vite as the dev server/bundler.

Structure for maintainability instead of reaching for a framework:
- **Pure, browser-free logic modules** (`liveness.ts`, `select.ts`) for the safety-critical
  decisions — freshness/phase state machine, worst-zone banner selection, audio-policy. These
  are **unit-tested directly under Node** (`node --test`, Node ≥22 type-stripping) with no
  bundler or DOM — the L2-equivalent for the HMI.
- **Browser modules** (`scene.ts` Canvas, `audio.ts` Web Audio, `bus.ts` MQTT, `ui.ts` DOM
  chrome + view router) each own one concern.
- A small hand-rolled **view router** (`drive | settings | diagnostics`) toggling DOM
  containers — a dozen lines, no dependency.
- A central mutable **store** the rAF loop reads and the bus writes — sufficient for one screen;
  no reactive library.

## Options Considered

### Option A: Vanilla TypeScript modules (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low — no JSX/build-plugin/runtime; the hard part (Canvas) is framework-agnostic |
| Bundle / boot | Smallest; best for NFR-12 boot-to-monitoring |
| Rework | None — keeps the working S1 slice; thickens rather than rewrites |
| Testability | Pure logic modules unit-test under Node with zero deps |
| Fit | Single-screen imperative-Canvas kiosk; framework would serve only cut-first views |

**Pros:** No rewrite of S1; tiny bundle; safety logic is plain testable functions; nothing
between the code and the Canvas/Web-Audio APIs the spec is written against.
**Cons:** Settings/Diagnostics forms are hand-wired (more imperative DOM than JSX); no component
ecosystem if the UI later grows.

### Option B: Migrate to React + TS (the original ADR-0003 letter)
**Pros:** Declarative Settings/Diagnostics; component reuse; team-teachable; matches the
paper decision.
**Cons:** Rewrites the working S1 canvas into a `useRef`/`useEffect` wrapper for no rendering
gain; adds React+ReactDOM runtime + the Vite React plugin + JSX toolchain; larger bundle works
against NFR-12; the framework's strengths land only on the two cut-first views.

### Option C: Lightweight reactive lib (Preact / Lit / Svelte)
**Pros:** Smaller than React; still declarative for the forms.
**Cons:** Still a dependency and a new idiom for a one-screen appliance; same "canvas is
imperative anyway" reality; not worth the concept count for a solo dev.

## Trade-off Analysis
ADR-0003's real, durable decision was **"web, not native"** (Option A vs B/C there) plus the
concrete tech — Canvas, Web Audio, MQTT-WS, kiosk. Those are unchanged and correct. "React"
was the one sub-choice made without evidence; the S1 slice supplied the evidence. For an
imperative-Canvas, single-screen, boot-time-sensitive kiosk whose only framework-friendly
surfaces are the first to be cut, a framework is **cost without payoff**. Vanilla TS keeps the
safety core as plain, directly testable functions and the bundle minimal. This is a refinement
*within* the web stack, not a reversal of ADR-0003 — exactly the "revisit a sub-decision when
constraints/scope become clear" the ADR log invites.

## Consequences
- **Easier:** no S1 rewrite; smallest bundle (helps NFR-12); safety logic (`liveness`,
  `select`) unit-tested under Node with no DOM/bundler; one fewer toolchain to manage on the Pi.
- **Harder:** Settings/Diagnostics are imperative DOM (acceptably small for two simple views);
  no component library to lean on if the HMI later grows a richer UI.
- **Revisit when:** the HMI grows genuinely multi-view/stateful UI (rich settings, multi-vehicle
  fleet view, phase-2 camera overlays with interactive controls), or a productized in-dash unit
  needs a component ecosystem — then adopt React/Preact/Lit. The Canvas `scene.ts`, `audio.ts`,
  and the pure logic modules port unchanged; only `ui.ts` would be reframed.

## Action Items
1. [x] Build S3 HMI as vanilla TS modules (scene / audio / bus / liveness / select / ui / store).
2. [x] Unit-test the safety-critical pure logic (`liveness`, `select`) under `node --test`.
3. [x] Update [ADR-0003](ADR-0003-hmi-stack.md) status to *Accepted (framework refined by ADR-0009)*
   and the [ADR index](README.md).
4. [ ] Re-evaluate at phase-2 (camera overlays / richer settings) per "Revisit when" above.
