"""L1 contract tests (ADR-0005, 11 §11.2 level L1).

Validates that every wire-message fixture and both config files conform to the frozen
JSON Schemas in ../schemas/. Each document's own `schema` version string selects its
schema (a schema's `title` equals the `schema` const it validates), so a document that
mislabels itself is caught here too.

Run:  pytest -q tests/
"""
from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
FIXTURE_DIR = pathlib.Path(__file__).resolve().parent / "fixtures"
CONFIG_FILES = ["config/sensors.example.json", "config/zones.example.json"]


def _load(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# registry: schema id (== each schema's `title`) -> schema object
SCHEMAS: dict[str, dict] = {}
for _f in sorted(SCHEMA_DIR.glob("*.json")):
    _s = _load(_f)
    SCHEMAS[_s["title"]] = _s


def validate_doc(doc: dict) -> None:
    """Validate a document against the schema named by its own `schema` field."""
    sid = doc.get("schema")
    assert sid in SCHEMAS, f"unknown or missing schema id: {sid!r}"
    jsonschema.validate(doc, SCHEMAS[sid])


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
    with pytest.raises(AssertionError):
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
