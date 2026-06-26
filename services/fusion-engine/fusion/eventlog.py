"""Black-box event log (FR-10): structured JSONL + SQLite, for the feasibility evaluation
(Nội dung 6) and deterministic replay (11 §11.6). Logs zone-severity transitions only, so
the file stays small. Both sinks are local and zero-config; logs/ is git-ignored.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class EventLog:
    def __init__(self, log_dir: Path):
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl = open(log_dir / "events.jsonl", "a", encoding="utf-8")
        self._db = sqlite3.connect(str(log_dir / "events.db"))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS transitions "
            "(ts INTEGER, zone_id TEXT, from_sev TEXT, to_sev TEXT, nearest_range_m REAL, reason TEXT)"
        )
        self._db.commit()

    def transition(self, ts: int, zone_id: str, frm: str, to: str,
                   nearest: float | None, reason: str) -> None:
        rec = {"ts": ts, "zone_id": zone_id, "from": frm, "to": to,
               "nearest_range_m": nearest, "reason": reason}
        self._jsonl.write(json.dumps(rec) + "\n")
        self._jsonl.flush()
        self._db.execute("INSERT INTO transitions VALUES (?,?,?,?,?,?)",
                         (ts, zone_id, frm, to, nearest, reason))
        self._db.commit()

    def close(self) -> None:
        try:
            self._jsonl.close()
        finally:
            self._db.close()
