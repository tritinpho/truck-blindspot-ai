# tools/ — operator & evaluation tooling

Scripts that support development, demos, and the feasibility evaluation (Nội dung 6).

| Tool | Status | Purpose |
|------|--------|---------|
| `publish_sample.py` | S0 | publish one sample `bsw/sensor` reading — broker smoke test |
| `sim_drive.py` | S1 | one-sensor sweep (RIGHT SAFE→DANGER→SAFE) — the vertical-slice driver |
| `sim_demo.py` | S3 | scripted multi-zone timeline that demos the whole HMI (zones, icons, banner, escalating audio, context boost, park-standby, sensor dropout → UNKNOWN) |
| `scenario_runner.py` | S4 | replay scripted scenarios S1–S6 → L3 regression suite ([08 §8.4](../docs/08-simulation.md)) |
| `log_replay.py` | S4 | recompute metrics from recorded logs ([11 §11.6](../docs/11-evaluation-plan.md)) |
| `latency_observer.py` | S4 | single-clock end-to-end latency measurement ([ADR-0008](../docs/adr/ADR-0008-time-and-clock-domains.md) #3) |

`publish_sample.py` (S0), `sim_drive.py` (S1), and `sim_demo.py` (S3) exist; the S4 tools are
placeholders in the build plan ([16 §16.3](../docs/16-build-plan.md)).

```bash
# Full S3 HMI demo (broker + fusion must be up):
python tools/sim_demo.py            # add --once to play the timeline a single pass
```
