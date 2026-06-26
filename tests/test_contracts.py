"""L1 contract tests (ADR-0005, 11 §11.2 level L1).

Validates that every wire-message fixture and both config files conform to the frozen
JSON Schemas in ../schemas/. Each document's own `schema` version string selects its
schema (a schema's `title` equals the `schema` const it validates), so a document that
mislabels itself is caught here too.

The validator core (`load_schemas` / `validate_doc`) lives in `tools/validate_message.py`
and is imported here, so CI and the firmware student's offline self-check run the SAME code
(no drift). This file also pins the captured-firmware-sample path and the contract-convention
lint that the student relies on at G4.

Run:  pytest -q tests/
"""
from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest

from tools.validate_message import (
    UnknownSchema,
    contract_lint,
    iter_captured,
    load_schemas,
    topic_lint,
)
from tools.validate_message import validate_doc as _validate_against

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
FIXTURE_DIR = pathlib.Path(__file__).resolve().parent / "fixtures"
FIRMWARE_DIR = FIXTURE_DIR / "firmware"
CONFIG_FILES = ["config/sensors.example.json", "config/zones.example.json"]

# Single source of truth for the L1 validator (shared with tools/validate_message.py CLI).
SCHEMAS = load_schemas(SCHEMA_DIR)


def _load(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_doc(doc: dict) -> None:
    """Validate a document against the schema named by its own `schema` field."""
    _validate_against(doc, SCHEMAS)


def test_every_schema_is_valid_jsonschema():
    for schema in SCHEMAS.values():
        jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("fixture", sorted(FIXTURE_DIR.glob("*.json")), ids=lambda p: p.name)
def test_message_fixture_validates(fixture):
    validate_doc(_load(fixture))


@pytest.mark.parametrize("cfg", CONFIG_FILES)
def test_config_validates(cfg):
    validate_doc(_load(ROOT / cfg))


def test_missing_required_field_fails():
    bad = {"schema": "bsw.sensor_reading/1", "sensor_id": "right_mid", "ts": 1}  # no present/health
    with pytest.raises(jsonschema.ValidationError):
        validate_doc(bad)


def test_unknown_schema_id_fails():
    with pytest.raises(UnknownSchema):
        validate_doc({"schema": "bsw.nope/1"})


def test_config_typo_is_rejected():
    """R2-4: strict config schemas — a misspelled key must fail loud, not silently default."""
    z = _load(ROOT / "config/zones.example.json")
    z["zones"][0]["dangr_m"] = 0.5  # typo for danger_m
    with pytest.raises(jsonschema.ValidationError):
        validate_doc(z)


def test_vehicle_has_no_reverse_flag():
    """R2-2: gear is the single source of truth; the redundant reverse boolean was removed."""
    assert "reverse" not in SCHEMAS["bsw.vehicle/1"]["properties"]


# --------------------------------------------------- captured firmware samples (G4, docs/20)
# Reference messages an ESP32 node should publish: RTC-less → ts_kind "monotonic_ms" (ADR-0008),
# present=false ⇒ range_m null, a read failure → health "fault". They must be schema-valid AND
# convention-clean, so the student has a known-good target to diff their own capture against.

@pytest.mark.parametrize("sample", sorted(FIRMWARE_DIR.glob("*.json")), ids=lambda p: p.name)
def test_captured_firmware_sample_validates(sample):
    doc = _load(sample)
    validate_doc(doc)                      # frozen-schema valid
    assert contract_lint(doc) == []        # and convention-clean (no firmware foot-guns)


def test_firmware_samples_exercise_the_esp32_specifics():
    samples = [_load(p) for p in sorted(FIRMWARE_DIR.glob("*.json"))]
    assert samples, "no firmware samples under tests/fixtures/firmware/"
    readings = [s for s in samples if s["schema"] == "bsw.sensor_reading/1"]
    # RTC-less node: every sample declares monotonic_ms (never a fake epoch)
    assert all(s.get("ts_kind") == "monotonic_ms" for s in samples)
    # the present/range_m coupling is shown both ways
    assert any(s["present"] is False and s["range_m"] is None for s in readings)
    assert any(s["present"] is True and s["range_m"] is not None for s in readings)
    # a node-side fault sample exists (read failure → publish fault, never silence)
    assert any(s.get("health") == "fault" for s in readings)


# --------------------------------------------------- contract-convention lint (beyond schema)
# Cross-field / clock rules JSON Schema can't express; the offline tool warns on them so a
# schema-valid-but-wrong firmware message is still caught before integration.

def test_lint_flags_present_false_with_a_range():
    bad = _load(next(FIRMWARE_DIR.glob("sensor_clear.json")))
    bad["range_m"] = 0.5  # present=false but a range slipped through
    warns = contract_lint(bad)
    assert any("present=false" in w for w in warns)


def test_lint_flags_missing_ts_kind():
    bad = {"schema": "bsw.sensor_reading/1", "sensor_id": "right_mid", "ts": 142037,
           "modality": "ultrasonic", "present": True, "range_m": 0.8, "health": "ok"}
    assert any("ts_kind" in w for w in contract_lint(bad))


def test_lint_flags_fault_with_present_true():
    bad = {"schema": "bsw.sensor_reading/1", "sensor_id": "right_mid", "ts": 1, "modality": "ultrasonic",
           "ts_kind": "monotonic_ms", "present": True, "range_m": 0.8, "health": "fault"}
    assert any("fault" in w for w in contract_lint(bad))


def test_topic_lint_flags_sensor_id_mismatch():
    doc = {"schema": "bsw.sensor_reading/1", "sensor_id": "right_mid", "ts": 1,
           "ts_kind": "monotonic_ms", "modality": "ultrasonic", "present": False,
           "range_m": None, "health": "ok"}
    assert topic_lint("bsw/sensor/left_mid", doc)        # topic leaf != sensor_id → warn
    assert topic_lint("bsw/sensor/right_mid", doc) == []  # matching → clean


# --------------------------------------------------- capture parsing (what the student pipes in)

def test_iter_captured_handles_the_three_shapes():
    one = '{"schema": "bsw.health/1", "component": "x", "ts": 1, "status": "ok"}'
    # single object
    assert iter_captured(one) == [(None, json.loads(one))]
    # NDJSON (plain mosquitto_sub)
    assert len(iter_captured(one + "\n" + one)) == 2
    # topic-prefixed (mosquitto_sub -v)
    topic, doc = iter_captured("bsw/health/x " + one)[0]
    assert topic == "bsw/health/x" and doc["component"] == "x"
    # JSON array
    assert len(iter_captured(f"[{one}, {one}]")) == 2
