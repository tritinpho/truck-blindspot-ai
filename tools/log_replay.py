#!/usr/bin/env python3
"""Recompute evaluation metrics from a recorded event log (FR-10, 11 §11.6).

The fusion engine writes zone-severity transitions to logs/events.jsonl (eventlog.py). Replaying
that log here reproduces the report metrics deterministically — so results are reproducible, not
anecdotal. The metric core is sim/metrics.py (pure, unit-tested); this is just the file I/O shell.

    python tools/log_replay.py                  # default logs/events.jsonl
    python tools/log_replay.py path/to/events.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs on the Windows cp1252 console

from sim.metrics import summarize_events  # noqa: E402


def load_events(path: Path) -> list[dict]:
    """Read JSONL transition rows. Tolerate a malformed line (skip + warn) instead of aborting the
    whole replay on one bad row — matches summarize_events, which is built to ignore partial rows."""
    events = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[replay] skipping malformed line {n}: {e.msg}", file=sys.stderr)
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", nargs="?", default=str(REPO / "logs" / "events.jsonl"))
    args = ap.parse_args()

    path = Path(args.log)
    if not path.exists():
        ap.error(f"log not found: {path} (run the fusion engine to generate logs/events.jsonl)")

    events = load_events(path)
    s = summarize_events(events)
    t = s["total"]
    print(f"event log: {path}")
    print(f"  {t['events']} transitions across {t['zones']} zones | "
          f"to-DANGER {t['to_danger']}  to-UNKNOWN {t['to_unknown']}  flicker {t['flicker']}")
    print(f"  {'zone':12} {'trans':>6} {'toDANGER':>9} {'toUNKNOWN':>10} {'flicker':>8}")
    for z in sorted(s["per_zone"]):
        d = s["per_zone"][z]
        print(f"  {z:12} {d['transitions']:>6} {d['to_danger']:>8} {d['to_unknown']:>9} {d['flicker']:>8}")


if __name__ == "__main__":
    main()
