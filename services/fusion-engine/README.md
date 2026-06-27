# services/fusion-engine — the "bộ xử lý trung tâm"

Python service: subscribe to `bsw/sensor/#`, `bsw/detection/#`, `bsw/vehicle`; resolve each
sensor → zone via [`config/sensors.example.json`](../../config/sensors.example.json); compute per-zone
severity with debounce + context; publish consolidated `bsw/zone/{zone_id}` (retained) and a
`bsw/health/fusion` heartbeat. Staleness/age is measured from **local arrival time**
([ADR-0008](../../docs/adr/ADR-0008-time-and-clock-domains.md)). Spec:
[05-warning-logic.md](../../docs/05-warning-logic.md).

**Status:** S5 — full warning logic plus the live command loop, consolidated for M3. Severity over
all zones, confirm/release debounce + asymmetric distance hysteresis, confirm-by-range
(`immediate_danger_factor`), context modifiers (turn-signal/reverse boost, park standby),
local-arrival staleness → UNKNOWN, JSONL+SQLite event logging (FR-10), and **`bsw/cmd`** retune
(`set_threshold` / `enable_zone` / `disable_zone` / `reload_config`, 04 §4.3.6).

Modules:
- `engine.py` — pure warning logic + `apply_cmd`/`replace_config` (L2: `tests/test_engine.py` +
  `tests/test_commands.py`).
- `service.py` — broker-agnostic `FusionService`: routes `bsw/sensor|detection|vehicle|cmd` and
  produces the per-tick `bsw/zone/#` payloads + transition log. Same object runs under a real broker
  and under the integration shim (ADR-0005) — no sim/real fork.
- `__main__.py` — the paho client + real-time loop + LWT + heartbeat only.
- `eventlog.py` — black-box transition + command audit log.

```bash
pip install -r requirements.txt
python -m fusion                    # connect to localhost:1883; --host/--port/--zones/--sensors/--log-dir
# or, with the whole stack:  docker compose -f ../../deploy/docker-compose.yml up -d
```
