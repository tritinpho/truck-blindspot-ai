# sim/ — geometric simulator & deterministic scenario runner (Python)

The **CI-friendly** half of the simulator ([08-simulation.md](../docs/08-simulation.md) §8.4): a
geometric sensor model + a deterministic runner that replays the scripted scenarios **S1–S6** (and
fault cases) through the **real fusion engine**. It is the engine behind the **L3 regression
suite** ([tests/test_scenarios.py](../tests/test_scenarios.py)) and the
[`tools/scenario_runner.py`](../tools/scenario_runner.py) CLI. (The interactive drag-drop *web*
scene-editor in [`apps/simulator`](../apps/simulator) is a deferred stretch, [16 §16.7](../docs/16-build-plan.md).)

Both producers emit the **identical** `bsw/sensor` + `bsw/detection` + `bsw/vehicle` contract a
real rig publishes, so sim and hardware stay interchangeable ([ADR-0005](../docs/adr/ADR-0005-sim-real-parity.md)).

## Modules

| Module | What |
|--------|------|
| `geometry.py` | Pure planar model: place objects in the normalized top-view, classify into a zone (point-in-polygon), range = distance-to-truck × scale; emit ultrasonic readings / camera detections with optional **noise, dropout, and ADR-0007 group-fire**. No MQTT, no fusion dep. |
| `scenarios.py` | S1–S6 + faults as object **tracks** + vehicle context (pure data). |
| `runner.py` | Drive the real `FusionEngine` on a **controlled clock** (deterministic, no broker); `Timeline` exposes the zone-severity history + HMI-side worst-zone/audio policy (mirrors `apps/hmi` `select.ts`). |
| `metrics.py` | Pure cores for the eval tools: `summarize_events` (log replay) + `LatencyPairer` (single-observer latency). |

## Why deterministic, and the honesty caveat

The runner supplies the tick index as both the monotonic arrival time and the wire `ts`, so a run
is fully reproducible — same scenario → same timeline, every time, on any machine. Seeded RNG makes
noise/dropout reproducible too.

**The sim derives detection from zone geometry, so it measures the model against itself.** L3 is
therefore for **logic + regression**; the headline detection-rate and latency figures for the
report must come from **L4 bench**, never from this sim ([11 §11.2](../docs/11-evaluation-plan.md),
[14 §P2](../docs/14-architecture-critique.md) #6).

## Run

```bash
pytest -q tests/test_scenarios.py        # the L3 suite (no hardware, no broker)
python tools/scenario_runner.py          # print every scenario's outcome (deterministic)
python tools/scenario_runner.py S2 -v    # one scenario, tick-by-tick
python tools/scenario_runner.py S2 --live  # publish S2 to the broker for a live HMI demo
```
