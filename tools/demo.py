#!/usr/bin/env python3
"""One-command demo launcher (G6 deliverable / §16.7 demo packaging).

Collapses the run book's "bring up the stack → open the HMI → drive a scenario" (17 §2–§4) into a
single command for a reviewer / PI demo, then leaves the stack running so they can poke the HMI:

    python tools/demo.py             # compose up (broker+fusion+HMI :8080) → open browser → narrated timeline
    python tools/demo.py --once      # play the timeline once and stop (stack stays up)
    python tools/demo.py --down      # tear the stack down (docker compose down -v) and exit
    python tools/demo.py --no-up     # stack already running: just open the HMI + drive
    python tools/demo.py --no-browser

The narrated timeline IS tools/sim_demo.py (imported, not duplicated — one source of truth for the
demo content): it walks S1 / S2+fault / S4 / S6 over the SAME wire messages a real rig emits (parity,
ADR-0005), so the whole HMI is exercised — zone tints, the primary-alert banner, escalating audio,
park-standby (visual-only), and a sensor dropout → UNKNOWN + fault chime.

Needs Docker (the shipped deploy/docker-compose.yml). No Docker? Run broker + fusion per 17 §2, then
`python tools/demo.py --no-up` (or just `python tools/sim_demo.py`).
"""
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs (§ → ▶) on a Windows cp1252 console

REPO = Path(__file__).resolve().parents[1]
COMPOSE = REPO / "deploy" / "docker-compose.yml"
HMI_URL = "http://localhost:8080"

sys.path.insert(0, str(REPO))
from tools.sim_demo import drive  # noqa: E402  — reuse the single demo timeline


def _compose(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE), *args]


def wait_for_port(host: str, port: int, timeout_s: float = 60.0) -> bool:
    """Block until host:port accepts a TCP connection, or timeout. Returns whether it came up — the
    readiness gate so we don't start driving (or open the browser) before the broker/HMI is listening."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--down", action="store_true", help="tear the compose stack down (down -v) and exit")
    ap.add_argument("--no-up", action="store_true", help="assume the stack is already running")
    ap.add_argument("--no-browser", action="store_true", help="don't open the HMI in a browser")
    ap.add_argument("--once", action="store_true", help="play the timeline once, then stop")
    ap.add_argument("--build", action="store_true", help="force `up --build` (rebuild images first)")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--hz", type=float, default=12.0, help="publish rate per sensor")
    args = ap.parse_args()

    needs_docker = not args.no_up or args.down
    if needs_docker and shutil.which("docker") is None:
        print("[demo] docker not found. Run broker + fusion per 17 §2, then: "
              "python tools/demo.py --no-up", file=sys.stderr)
        return 1

    if args.down:
        print("[demo] tearing down the stack …")
        return subprocess.call(_compose("down", "-v"))

    if not args.no_up:
        # logs/ must exist + be writable by the non-root fusion container (UID 10001): on a host that
        # enforces bind-mount ownership a fresh root-owned dir would block it (mirrors the CI step).
        (REPO / "logs").mkdir(exist_ok=True)
        up = _compose("--profile", "hmi", "up", "-d")
        if args.build:
            up.append("--build")
        print(f"[demo] bringing up broker + fusion + HMI …  ({' '.join(up)})")
        rc = subprocess.call(up)
        if rc != 0:
            print("[demo] compose up failed — see the output above.", file=sys.stderr)
            return rc

    print(f"[demo] waiting for the broker at {args.host}:{args.port} …")
    if not wait_for_port(args.host, args.port):
        print("[demo] broker did not come up in time — check: "
              "docker compose -f deploy/docker-compose.yml logs", file=sys.stderr)
        return 1

    if not args.no_browser:
        if not args.no_up:
            wait_for_port("localhost", 8080, timeout_s=20.0)  # best-effort: let nginx answer first
        print(f"[demo] opening {HMI_URL}")
        try:
            webbrowser.open(HMI_URL)
        except Exception:  # noqa: BLE001 — headless box: just print the URL
            print(f"[demo] open it yourself: {HMI_URL}")

    print(f"[demo] HMI at {HMI_URL} — driving the narrated timeline. "
          f"Ctrl-C to stop (the stack stays up; `python tools/demo.py --down` to remove it).")
    return drive(args.host, args.port, args.hz, args.once)


if __name__ == "__main__":
    raise SystemExit(main())
