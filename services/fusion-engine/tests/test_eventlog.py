"""L2 tests for the black-box event log (eventlog.py).

The live service writes severity transitions on the tick thread and command audits on the paho
network thread (see __main__.py: loop_start() runs the MQTT client on its own thread while the
publish loop runs on the main thread). They share ONE sqlite3 connection, so the log must be safe
to use across threads. These are the regression guard for the cross-thread ProgrammingError that
silently broke command logging the first time any runtime bsw/cmd arrived.
"""
import pathlib
import sqlite3
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fusion.eventlog import EventLog  # noqa: E402


def _commands(db_path: pathlib.Path):
    con = sqlite3.connect(str(db_path))
    try:
        return con.execute("SELECT ts, op, applied, detail FROM commands").fetchall()
    finally:
        con.close()


def test_command_logged_from_another_thread(tmp_path):
    """The connection is opened here (the 'main' thread); command() runs on a different thread,
    exactly as paho's on_message does. It must not raise, and the row must land in both sinks."""
    log = EventLog(tmp_path)
    errors: list[Exception] = []

    def worker():
        try:
            log.command(123, "set_threshold", True, "RIGHT danger_m=0.7")
        except Exception as e:  # noqa: BLE001 — capture cross-thread sqlite failures
            errors.append(e)

    th = threading.Thread(target=worker)
    th.start()
    th.join()
    log.close()

    assert errors == []  # no sqlite3.ProgrammingError across threads
    assert _commands(tmp_path / "events.db") == [(123, "set_threshold", 1, "RIGHT danger_m=0.7")]
    assert '"op": "set_threshold"' in (tmp_path / "commands.jsonl").read_text(encoding="utf-8")


def test_transitions_and_commands_interleave_safely(tmp_path):
    """Tick-thread transitions and network-thread commands run concurrently without raising or
    corrupting the shared connection (the _lock serializes the writes)."""
    log = EventLog(tmp_path)
    errors: list[Exception] = []

    def transitions():
        try:
            for i in range(100):
                log.transition(i, "RIGHT", "SAFE", "DANGER", 0.7, "approach")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def commands():
        try:
            for i in range(100):
                log.command(i, "set_threshold", True, "d")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=transitions), threading.Thread(target=commands)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log.close()

    assert errors == []
    con = sqlite3.connect(str(tmp_path / "events.db"))
    try:
        assert con.execute("SELECT COUNT(*) FROM transitions").fetchone()[0] == 100
        assert con.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 100
    finally:
        con.close()
