# tests/ — L1 contract + L3 scenario / integration tests

The repo-level [evaluation plan](../docs/11-evaluation-plan.md) levels that live here (L2 fusion
unit tests live with the engine in [`../services/fusion-engine/tests`](../services/fusion-engine/tests)):

| File | Level | What |
|------|-------|------|
| `test_contracts.py` | L1 | every wire message + both configs validate vs [`../schemas/`](../schemas/), plus negative cases (missing field, config typo, `vehicle.reverse` absent) |
| `test_scenarios.py` | L3 | S1–S6 + F1/F2/F3/F5 through the real fusion engine in-process (deterministic) |
| `test_integration_shim.py` | L3 | the **live path** (publisher → loopback bus → fusion routing → retained `bsw/zone` → subscriber) matches the in-process outcomes — no broker |
| `test_integration_broker.py` | L3 | the same over **real MQTT** + fusion; self-skips without a broker (runs in the CI `integration` job / a local `docker compose up`) |
| `test_reproducibility.py` | — | a run writes `events.jsonl`; identical scenario → byte-identical log + identical replayed metrics (11 §11.6) |
| `test_tools.py` | — | pure metric cores behind `log_replay` + `latency_observer` |

```bash
pip install -r tests/requirements.txt
pytest -q tests/ services/fusion-engine/tests        # everything broker-free (broker test self-skips)
```

- `fixtures/` — one valid sample per message type (`bsw.*`). Add cases here as the contract grows.
- `_loopback.py` — the in-process MQTT bus the integration shim runs on (test transport, not a
  forked code path — the same `FusionService` runs over it and over a real broker).
