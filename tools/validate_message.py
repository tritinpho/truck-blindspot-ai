#!/usr/bin/env python3
"""Validate captured BSW messages against the frozen schemas — the offline self-check (G4).

This is the **single source of L1 validation** (11 §11.2): `tests/test_contracts.py` imports
`load_schemas` + `validate_doc` from here, and the firmware student runs the CLI on a captured
message to prove their ESP32 node speaks the frozen contract (04-message-protocol.md) BEFORE
plugging into the pipeline — zero downstream change, parity (ADR-0005).

It needs only `jsonschema` + the `schemas/` dir — no broker, no fusion, no network. Capture a
message off the bus and pipe it in:

    # one message (mosquitto_sub prints the JSON payload, one per line):
    mosquitto_sub -h <broker> -C 1 -t 'bsw/sensor/right_mid' | python tools/validate_message.py

    # keep the topic too (-v prints "topic payload") — the tool also checks topic ⇄ sensor_id:
    mosquitto_sub -h <broker> -v -t 'bsw/sensor/#' | python tools/validate_message.py -

    # or validate a saved capture / a hand-written sample file:
    python tools/validate_message.py my_capture.txt
    python tools/validate_message.py firmware_sample.json --strict

Exit status is 0 only when every message is schema-valid (and, under --strict, lint-clean), so
it drops straight into a firmware CI step or a pre-flight bench check.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


# --------------------------------------------------------------------------- schema registry

def load_schemas(schema_dir: Path = DEFAULT_SCHEMA_DIR) -> dict[str, dict]:
    """Map each frozen schema's id (its `title`, == the `schema` const it validates) -> schema.
    Same registry the L1 contract tests build, so the tool and CI never drift."""
    schemas: dict[str, dict] = {}
    for f in sorted(Path(schema_dir).glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        schemas[s["title"]] = s
    return schemas


class UnknownSchema(ValueError):
    """The document's `schema` field names no frozen schema (or is missing)."""


def validate_doc(doc: dict, schemas: dict[str, dict]) -> None:
    """Validate `doc` against the schema named by its own `schema` field. Raises UnknownSchema if
    that id is missing/unknown, or jsonschema.ValidationError if the body is malformed. (This is
    the assert-style core the contract tests reuse; the CLI wraps it in `check_message`.)"""
    sid = doc.get("schema")
    if sid not in schemas:
        raise UnknownSchema(
            f"unknown or missing schema id: {sid!r} (known: {', '.join(sorted(schemas)) or 'none'})")
    jsonschema.validate(doc, schemas[sid])


# ----------------------------------------------------------- contract conventions (beyond schema)

def contract_lint(doc: dict) -> list[str]:
    """Cross-field / clock conventions from 04-message-protocol.md that JSON Schema cannot express,
    returned as human-readable warnings (empty = clean). These are the firmware mistakes that pass
    schema validation but break the pipeline's intent."""
    warns: list[str] = []
    sid = str(doc.get("schema", ""))

    if sid.startswith("bsw.sensor_reading/"):
        present, rng = doc.get("present"), doc.get("range_m")
        if present is False and rng is not None:
            warns.append("present=false but range_m is not null "
                         "(04 §4.3.1: present=false ⇒ range_m null)")
        if present is True and rng is None:
            warns.append("present=true but range_m is null/absent "
                         "(a detected object must carry its range_m)")
        if doc.get("health") == "fault" and present is True:
            warns.append('health="fault" with present=true is contradictory — a node that cannot '
                         "read its sensor should publish present=false, range_m=null (04 §4.3.1)")
        if "modality" not in doc:
            warns.append('modality missing (recommended; e.g. "ultrasonic")')

    if sid.startswith(("bsw.sensor_reading/", "bsw.health/")):
        if "ts_kind" not in doc:
            warns.append('ts_kind missing → consumers assume "epoch_ms"; an RTC-less ESP32 MUST '
                         'send "monotonic_ms" so staleness/latency stay correct (ADR-0008)')
        elif doc.get("ts_kind") == "epoch_ms" and doc.get("ts", 0) < 1_000_000_000_000:
            warns.append('ts_kind="epoch_ms" but ts is small (not a real wall-clock epoch); an '
                         'RTC-less node should declare "monotonic_ms" (ADR-0008)')

    if sid.startswith("bsw.cmd/"):
        # The schema can't express the cmd's per-op `args` shape (it's an open bag), so lint the
        # cross-field rules the engine enforces at runtime — caught here BEFORE the command hits the
        # bus rather than only as a silent runtime rejection (engine.apply_cmd, 05 §5.2 / 04 §4.3.6).
        op = doc.get("op")
        args = doc.get("args") or {}
        if op in ("set_threshold", "enable_zone", "disable_zone") and not args.get("zone_id"):
            warns.append(f"{op} missing args.zone_id (04 §4.3.6)")
        if op == "set_threshold":
            d, c = args.get("danger_m"), args.get("caution_m")
            if isinstance(d, (int, float)) and isinstance(c, (int, float)) and not isinstance(d, bool) \
                    and not isinstance(c, bool) and d > c:
                warns.append(f"set_threshold danger_m ({d}) > caution_m ({c}) — danger is the INNER "
                             "threshold and must stay <= caution_m (05 §5.2); fusion will reject it")
    return warns


def topic_lint(topic: str | None, doc: dict) -> list[str]:
    """If the capture kept its topic (mosquitto_sub -v), check the contract topic⇄id coupling:
    bsw/sensor/{sensor_id} and bsw/health/{component} must match the payload (04 §4.2)."""
    if not topic:
        return []
    warns: list[str] = []
    parts = topic.strip().split("/")
    if len(parts) >= 3 and parts[0] == "bsw":
        leaf = "/".join(parts[2:])
        if parts[1] == "sensor" and doc.get("sensor_id") not in (None, leaf):
            warns.append(f"topic is bsw/sensor/{leaf} but sensor_id={doc.get('sensor_id')!r} "
                         "(they must match — 04 §4.2)")
        if parts[1] == "health" and doc.get("component") not in (None, leaf):
            warns.append(f"topic is bsw/health/{leaf} but component={doc.get('component')!r} "
                         "(they must match — 04 §4.2)")
    return warns


# ------------------------------------------------------------------------------- capture parsing

def iter_captured(text: str) -> list[tuple[str | None, dict]]:
    """Parse a capture into (topic, doc) pairs. Accepts three shapes a student is likely to have:
      * a single JSON object, or a JSON array of objects (a saved/hand-written sample);
      * NDJSON — one JSON payload per line (plain `mosquitto_sub`);
      * topic-prefixed lines "bsw/sensor/right_mid {json}" (`mosquitto_sub -v`).
    Returns the docs with their topic (or None when the capture had no topic)."""
    stripped = text.strip()
    if not stripped:
        return []
    # whole-document JSON first (object or array)
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(obj, list):
            return [(None, d) for d in obj]
        return [(None, obj)]

    # otherwise line-oriented (NDJSON, optionally topic-prefixed)
    out: list[tuple[str | None, dict]] = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        topic = None
        if not line.startswith(("{", "[")):
            brace = line.find("{")
            if brace == -1:
                raise ValueError(f"line {n}: no JSON object found: {line[:60]!r}")
            topic, line = line[:brace].strip(), line[brace:]
        try:
            out.append((topic or None, json.loads(line)))
        except json.JSONDecodeError as e:
            raise ValueError(f"line {n}: invalid JSON ({e.msg}): {line[:60]!r}") from e
    return out


# --------------------------------------------------------------------------------- CLI checking

def check_message(topic: str | None, doc: dict, schemas: dict[str, dict]) -> dict:
    """Validate one captured message without raising. Returns
    {ok, schema, label, error, warnings} for the CLI report."""
    sid = doc.get("schema")
    label = sid if isinstance(sid, str) else "<no schema field>"
    try:
        validate_doc(doc, schemas)
    except UnknownSchema as e:
        return {"ok": False, "schema": sid, "label": label, "error": str(e), "warnings": []}
    except jsonschema.ValidationError as e:
        where = "/".join(str(p) for p in e.absolute_path) or "(root)"
        return {"ok": False, "schema": sid, "label": label,
                "error": f"{e.message} [at {where}]", "warnings": []}
    return {"ok": True, "schema": sid, "label": label, "error": None,
            "warnings": contract_lint(doc) + topic_lint(topic, doc)}


def _identifier(doc: dict) -> str:
    for k in ("sensor_id", "component", "zone_id"):
        if doc.get(k):
            return f"{k}={doc[k]}"
    return ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # portable glyphs on the Windows cp1252 console

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", nargs="?", default="-",
                    help="file with captured message(s), or '-' for stdin (default)")
    ap.add_argument("--schema-dir", type=Path, default=DEFAULT_SCHEMA_DIR,
                    help="directory of frozen schema *.json (default: repo schemas/)")
    ap.add_argument("--strict", action="store_true",
                    help="treat contract-convention warnings as failures (exit 1)")
    args = ap.parse_args()

    schemas = load_schemas(args.schema_dir)
    if not schemas:
        print(f"[validate] no schemas found in {args.schema_dir}", file=sys.stderr)
        return 2

    if args.capture == "-":
        text = sys.stdin.read()
    else:
        try:
            text = Path(args.capture).read_text(encoding="utf-8")
        except OSError as e:  # missing file / not readable — clean exit, not a traceback
            print(f"[validate] cannot read {args.capture}: {e}", file=sys.stderr)
            return 2
    try:
        messages = iter_captured(text)
    except ValueError as e:
        print(f"[validate] could not parse capture: {e}", file=sys.stderr)
        return 2
    if not messages:
        print("[validate] no messages in input", file=sys.stderr)
        return 2

    src = "stdin" if args.capture == "-" else args.capture
    print(f"[validate] {len(messages)} message(s) from {src} vs {len(schemas)} frozen schemas")
    n_bad = n_warn = 0
    for i, (topic, doc) in enumerate(messages, 1):
        r = check_message(topic, doc, schemas)
        ident = _identifier(doc)
        head = f"  [{i}] {r['label']:24} {ident:22}"
        if r["ok"]:
            print(f"{head} PASS")
        else:
            n_bad += 1
            print(f"{head} FAIL  {r['error']}")
        for w in r["warnings"]:
            n_warn += 1
            print(f"        warn: {w}")

    print(f"[validate] {len(messages)} checked: {len(messages) - n_bad} valid, {n_bad} invalid, "
          f"{n_warn} warning(s)")
    if n_bad:
        return 1
    if args.strict and n_warn:
        print("[validate] --strict: warnings present → non-zero exit")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
