# apps/simulator — scene editor & synthetic producer

Publishes the **same** `bsw/sensor/#` and `bsw/vehicle` messages a real rig would (sim/real
parity, [ADR-0005](../../docs/adr/ADR-0005-sim-real-parity.md)), so the whole pipeline runs with
no hardware. Doubles as the proposal's "computer simulation" deliverable. Spec:
[08-simulation.md](../../docs/08-simulation.md).

**Status:** S0 skeleton — connects to the broker. Geometric scene → readings in S4; the Python
scripted scenario runner (S1–S6, the L3 suite) lives in [`tools/`](../../tools/).

```bash
npm install
npm run dev
```
