"""Pytest path bootstrap: make `sim` (repo root) and `fusion` (services/fusion-engine) importable
across all test levels (L1/L2/L3) without per-file sys.path hacks."""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent
for _p in (str(REPO), str(REPO / "services" / "fusion-engine"), str(REPO / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
