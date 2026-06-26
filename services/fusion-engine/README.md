# services/fusion-engine — the "bộ xử lý trung tâm"

Python service: subscribe to `bsw/sensor/#`, `bsw/detection/#`, `bsw/vehicle`; resolve each
sensor → zone via [`config/sensors.json`](../../config/sensors.example.json); compute per-zone
severity with debounce + context; publish consolidated `bsw/zone/{zone_id}` (retained) and a
`bsw/health/fusion` heartbeat. Staleness/age is measured from **local arrival time**
([ADR-0008](../../docs/adr/ADR-0008-time-and-clock-domains.md)). Spec:
[05-warning-logic.md](../../docs/05-warning-logic.md).

**Status:** skeleton (S0). MVP one-zone severity lands in S1; full logic + L2 tests in S2.

```bash
pip install -r requirements.txt
# python -m fusion          # entrypoint added in S1
```
