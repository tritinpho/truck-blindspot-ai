# services/fusion-engine — the "bộ xử lý trung tâm"

Python service: subscribe to `bsw/sensor/#`, `bsw/detection/#`, `bsw/vehicle`; resolve each
sensor → zone via [`config/sensors.json`](../../config/sensors.example.json); compute per-zone
severity with debounce + context; publish consolidated `bsw/zone/{zone_id}` (retained) and a
`bsw/health/fusion` heartbeat. Staleness/age is measured from **local arrival time**
([ADR-0008](../../docs/adr/ADR-0008-time-and-clock-domains.md)). Spec:
[05-warning-logic.md](../../docs/05-warning-logic.md).

**Status:** S2 — full warning logic: severity over all zones, confirm/release debounce +
asymmetric distance hysteresis, confirm-by-range (`immediate_danger_factor`), context modifiers
(turn-signal/reverse boost, park standby), local-arrival staleness → UNKNOWN, and JSONL+SQLite
event logging (FR-10). `engine.py` = pure logic (19 L2 tests), `__main__.py` = MQTT transport,
`eventlog.py` = black-box log. Multi-zone fusion + camera VRU classification arrive with phase-2.

```bash
pip install -r requirements.txt
# python -m fusion          # entrypoint added in S1
```
