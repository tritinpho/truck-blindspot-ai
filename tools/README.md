# tools/ — operator & evaluation tooling

Scripts that support development, demos, and the feasibility evaluation (Nội dung 6).

| Tool | Status | Purpose |
|------|--------|---------|
| `publish_sample.py` | S0 | publish one sample `bsw/sensor` reading — broker smoke test |
| `sim_drive.py` | S1 | one-sensor sweep (RIGHT SAFE→DANGER→SAFE) — the vertical-slice driver |
| `sim_demo.py` | S3 | scripted multi-zone timeline that demos the whole HMI (zones, icons, banner, escalating audio, context boost, park-standby, sensor dropout → UNKNOWN) |
| `scenario_runner.py` | S4 | replay scripted scenarios S1–S6 deterministically (L3) or `--live` to the broker; uses [`sim/`](../sim/) ([08 §8.4](../docs/08-simulation.md)) |
| `log_replay.py` | S4 | recompute metrics from recorded `logs/events.jsonl` ([11 §11.6](../docs/11-evaluation-plan.md)) |
| `latency_observer.py` | S4 | single-observer, single-clock end-to-end latency ([ADR-0008](../docs/adr/ADR-0008-time-and-clock-domains.md) #3) |

All of the above exist (S0→S4). The geometric model + scenarios + deterministic runner they share
live in [`sim/`](../sim/); the L3 regression suite is [`tests/test_scenarios.py`](../tests/test_scenarios.py).

```bash
# Full S3 HMI demo (broker + fusion up): a scripted multi-zone timeline
python tools/sim_demo.py                  # add --once for a single pass

# S4 scenario runner — deterministic (no broker) or live:
python tools/scenario_runner.py           # print every scenario's outcome
python tools/scenario_runner.py S2 --live # publish S2 to the broker for a live HMI demo

# Recompute eval metrics from a recorded run; measure danger-path latency at one observer:
python tools/log_replay.py                # reads logs/events.jsonl
python tools/latency_observer.py          # tap bsw/sensor/# + bsw/zone/# (broker up)
```
