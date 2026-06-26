# apps/simulator — scene editor & synthetic producer

Publishes the **same** `bsw/sensor/#` and `bsw/vehicle` messages a real rig would (sim/real
parity, [ADR-0005](../../docs/adr/ADR-0005-sim-real-parity.md)), so the whole pipeline runs with
no hardware. Doubles as the proposal's "computer simulation" deliverable. Spec:
[08-simulation.md](../../docs/08-simulation.md).

**Status:** S0 skeleton — connects to the broker. The interactive drag-drop **web** scene-editor
is a deferred stretch ([16 §16.7](../../docs/16-build-plan.md)). The M3-critical artifact — the
**Python geometric sim + scenario runner** (S1–S6, the L3 regression suite) — shipped in S4 and
lives in [`sim/`](../../sim/) + [`tools/scenario_runner.py`](../../tools/scenario_runner.py). Both
emit the identical wire contract, so they stay interchangeable with a real rig.

```bash
npm install
npm run dev
```
