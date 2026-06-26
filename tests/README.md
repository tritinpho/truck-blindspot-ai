# tests/ — L1 contract tests

Level **L1** of the [evaluation plan](../docs/11-evaluation-plan.md): every wire message and both
config files must validate against the frozen JSON Schemas in [`../schemas/`](../schemas/).

```bash
pip install -r tests/requirements.txt
pytest -q tests/
```

- `fixtures/` — one valid sample per message type (`bsw.*`). Add cases here as the contract grows.
- `test_contracts.py` — validates fixtures + configs, plus negative cases (missing required field,
  config typo rejected, `vehicle.reverse` flag absent) that lock in the round-2 contract decisions.

L2 (fusion unit tests) lands in S2 alongside the fusion engine; L3 (scenario replay) in S4.
