"""Eval / dev tools (run as scripts, e.g. `python tools/scenario_runner.py`).

This package marker lets the shipped contract validator (`tools/validate_message.py`) be
imported as the single source of L1 validation by both the CLI and the contract tests
(`tests/test_contracts.py`), so the student's offline self-check uses the same code CI does.
"""
