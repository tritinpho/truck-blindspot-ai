"""Smoke + determinism tests for tools/eval_report.py — the reproducible eval-figure generator
(docs/21, 11 §11.6/§11.7). Drives the real fusion engine on a controlled clock into a tmp log dir
(no broker), so it runs in CI and guards that the report's numbers stay reproducible and honest."""
from __future__ import annotations

from tools.eval_report import build_report, canonical_run, render_markdown


def test_canonical_run_is_byte_identical(tmp_path):
    canonical_run(tmp_path / "a")
    canonical_run(tmp_path / "b")
    assert (tmp_path / "a" / "events.jsonl").read_text(encoding="utf-8") == \
           (tmp_path / "b" / "events.jsonl").read_text(encoding="utf-8")
    # re-running into the SAME dir must REPLACE (not append) → still identical
    first = (tmp_path / "a" / "events.jsonl").read_text(encoding="utf-8")
    canonical_run(tmp_path / "a")
    assert (tmp_path / "a" / "events.jsonl").read_text(encoding="utf-8") == first


def test_report_invariants(tmp_path):
    rep = build_report(canonical_run(tmp_path / "run"))

    outcomes = {o["id"]: o for o in rep["outcomes"]}
    # the headline L3 outcomes the report leans on
    assert outcomes["S2"]["finals"]["RIGHT"] == "DANGER" and outcomes["S2"]["worst"] == "RIGHT"
    assert outcomes["S6"]["standby"] is True and outcomes["S6"]["audio"] == "SILENT"
    assert outcomes["F1"]["finals"]["RIGHT"] == "UNKNOWN"            # fail-loud, not stale-green
    assert outcomes["F3·pedestrian"]["finals"]["RIGHT"] == "DANGER"  # VRU escalates sooner
    assert outcomes["F3·vehicle"]["finals"]["RIGHT"] == "CAUTION"

    # group-fire: 8 ultrasonic sensors, each ~half the master rate (TC-F5)
    gf = rep["group_fire"]
    assert len(gf) == 8
    assert all(0.4 * r["of_ticks"] <= r["fires"] <= 0.6 * r["of_ticks"] for r in gf)

    # replay metrics: debounce holds (no flicker) and DANGER fired across the battery
    assert rep["replay"]["total"]["flicker"] == 0
    assert rep["replay"]["total"]["to_danger"] >= 5

    # at least one clean danger-path latency (S1 approach) within the est-real budget
    s1 = next(r for r in rep["latency"]["rows"] if r["id"] == "S1")
    assert s1["sim_ms"] is not None and s1["est_real_ms"] <= 200


def test_build_report_deterministic(tmp_path):
    assert build_report(canonical_run(tmp_path / "a")) == build_report(canonical_run(tmp_path / "b"))


def test_render_markdown_has_sections_and_honesty(tmp_path):
    md = render_markdown(build_report(canonical_run(tmp_path / "run")))
    for marker in ("## 1. Scenario outcomes", "## 4. Canonical-run replay",
                   "## 6. Test-case coverage", "NEEDS-L4"):
        assert marker in md
