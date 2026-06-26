// L2-equivalent for the HMI's fail-loud core (ADR-0009 action #2). Pure logic, no DOM/bundler.
// Run: node --test   (Node ≥22 strips the types). See apps/hmi/README.md.
import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluateLiveness, DEFAULT_FRESHNESS_MS } from "../src/liveness.ts";

const base = {
  nowMono: 10_000,
  lastFusionReceiptMono: 10_000,
  sawFirstZone: true,
  fusionFaultLatched: false,
};

test("warming up until the first zone snapshot (NFR-12)", () => {
  const r = evaluateLiveness({ ...base, sawFirstZone: false, lastFusionReceiptMono: null });
  assert.equal(r.phase, "WARMING_UP");
  assert.equal(r.live, false);
});

test("warming up even if a heartbeat arrived but no zone yet", () => {
  // heartbeat sets a receipt time, but sawFirstZone is still false → not yet monitoring
  const r = evaluateLiveness({ ...base, sawFirstZone: false });
  assert.equal(r.phase, "WARMING_UP");
});

test("fresh fusion signal → MONITORING and live", () => {
  const r = evaluateLiveness({ ...base, nowMono: 10_500, lastFusionReceiptMono: 10_000 });
  assert.equal(r.phase, "MONITORING");
  assert.equal(r.live, true);
  assert.equal(r.ageMs, 500);
});

test("freshness boundary is inclusive at the window edge", () => {
  const at = evaluateLiveness({ ...base, nowMono: 10_000 + DEFAULT_FRESHNESS_MS, lastFusionReceiptMono: 10_000 });
  assert.equal(at.phase, "MONITORING", "age == window is still fresh");
  const past = evaluateLiveness({ ...base, nowMono: 10_001 + DEFAULT_FRESHNESS_MS, lastFusionReceiptMono: 10_000 });
  assert.equal(past.phase, "SIGNAL_LOST", "age > window trips signal lost");
});

test("stale stream → SIGNAL_LOST (whole map UNKNOWN), not stale-green (TC-F4)", () => {
  const r = evaluateLiveness({ ...base, nowMono: 12_000, lastFusionReceiptMono: 10_000 });
  assert.equal(r.phase, "SIGNAL_LOST");
  assert.equal(r.live, false);
});

test("a fault heartbeat (LWT) trips SIGNAL_LOST immediately, even when fresh", () => {
  const r = evaluateLiveness({ ...base, nowMono: 10_010, lastFusionReceiptMono: 10_000, fusionFaultLatched: true });
  assert.equal(r.phase, "SIGNAL_LOST");
});

test("recovers MONITORING when fresh data resumes", () => {
  const lost = evaluateLiveness({ ...base, nowMono: 13_000, lastFusionReceiptMono: 10_000 });
  assert.equal(lost.phase, "SIGNAL_LOST");
  const back = evaluateLiveness({ ...base, nowMono: 13_050, lastFusionReceiptMono: 13_000 });
  assert.equal(back.phase, "MONITORING");
});

test("custom freshness window is honored", () => {
  const r = evaluateLiveness({ ...base, nowMono: 10_300, lastFusionReceiptMono: 10_000, freshnessMs: 250 });
  assert.equal(r.phase, "SIGNAL_LOST");
});
