"""Black-box event log (FR-10): structured JSONL + SQLite, for the feasibility evaluation
(Nội dung 6) and deterministic replay (11 §11.6).

Two streams, kept in separate files so each stays single-purpose:
  * events.jsonl  — zone-severity transitions (what tools/log_replay.py recomputes; small,
    deterministic, byte-reproducible across identical runs).
  * commands.jsonl — bsw/cmd applied at runtime (threshold sweeps etc., 11 §11.6) so the chosen
    operating point is justified by an audit trail, not guesswork. Kept OUT of events.jsonl so
    the replay metric never sees a non-transition row.

Both sinks are local and zero-config; logs/ is git-ignored.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class EventLog:
    def __init__(self, log_dir: Path):
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        # transition() is called on the tick thread, command() on the paho network thread
        # (__main__ runs the publish loop and the MQTT client on separate threads). One SQLite
        # connection is shared across both, so it must allow cross-thread use AND be serialized:
        # check_same_thread=False lifts sqlite's same-thread guard, and _lock makes the writes
        # atomic. Without this, the first runtime bsw/cmd raises sqlite3.ProgrammingError.
        self._lock = threading.Lock()
        self._jsonl = open(log_dir / "events.jsonl", "a", encoding="utf-8")
        self._cmds = open(log_dir / "commands.jsonl", "a", encoding="utf-8")
        self._db = sqlite3.connect(str(log_dir / "events.db"), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS transitions "
            "(ts INTEGER, zone_id TEXT, from_sev TEXT, to_sev TEXT, nearest_range_m REAL, reason TEXT)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS commands "
            "(ts INTEGER, op TEXT, applied INTEGER, detail TEXT)"
        )
        self._db.commit()

    def transition(self, ts: int, zone_id: str, frm: str, to: str,
                   nearest: float | None, reason: str) -> None:
        rec = {"ts": ts, "zone_id": zone_id, "from": frm, "to": to,
               "nearest_range_m": nearest, "reason": reason}
        with self._lock:
            self._jsonl.write(json.dumps(rec) + "\n")
            self._jsonl.flush()
            self._db.execute("INSERT INTO transitions VALUES (?,?,?,?,?,?)",
                             (ts, zone_id, frm, to, nearest, reason))
            self._db.commit()

    def command(self, ts: int, op: str, applied: bool, detail: str) -> None:
        """Audit a runtime bsw/cmd (11 §11.6). Separate stream from transitions. Runs on the paho
        network thread, so it shares _lock with transition() (the tick thread)."""
        rec = {"ts": ts, "op": op, "applied": applied, "detail": detail}
        with self._lock:
            self._cmds.write(json.dumps(rec) + "\n")
            self._cmds.flush()
            self._db.execute("INSERT INTO commands VALUES (?,?,?,?)", (ts, op, int(applied), detail))
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._jsonl.close()
                self._cmds.close()
            finally:
                self._db.close()
