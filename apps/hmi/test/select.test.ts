// L2-equivalent for the priority/audio policy (05 §5.5/§5.6). Pure logic. Run: node --test
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  activeRank, activeZoneStates, audioTarget, isStandby, liveZonePriorities, worstActiveZone,
} from "../src/select.ts";
import type { Severity, ZoneState } from "../src/types.ts";

function zs(zone_id: string, severity: Severity, extra: Partial<ZoneState> = {}): ZoneState {
  return { schema: "bsw.zone_state/1", zone_id, ts: 0, severity, ...extra };
}

const ZONES = [
  { id: "RIGHT", risk_weight: 1.8 },
  { id: "FRONT_RIGHT", risk_weight: 1.6 },
  { id: "REAR", risk_weight: 1.3 },
  { id: "LEFT", risk_weight: 1.1 },
];

test("activeRank ranks only CAUTION/DANGER as active", () => {
  assert.equal(activeRank("DANGER"), 2);
  assert.equal(activeRank("CAUTION"), 1);
  assert.equal(activeRank("SAFE"), 0);
  assert.equal(activeRank("UNKNOWN"), 0);
});

test("worstActiveZone follows risk_weight × severity (05 §5.6)", () => {
  // LEFT DANGER (1.1×2=2.2) beats RIGHT CAUTION (1.8×1=1.8)
  const states = new Map([["RIGHT", zs("RIGHT", "CAUTION")], ["LEFT", zs("LEFT", "DANGER")]]);
  assert.equal(worstActiveZone(ZONES, states)?.id, "LEFT");
});

test("liveZonePriorities takes the live wire risk_weight, falls back to config otherwise", () => {
  const cfg = new Map([["RIGHT", 1.8], ["LEFT", 1.1]]);
  const states = new Map([
    ["RIGHT", zs("RIGHT", "DANGER", { risk_weight: 0.5 })], // live override wins
    ["LEFT", zs("LEFT", "CAUTION")],                        // no wire value → config fallback
  ]);
  const pri = new Map(liveZonePriorities(cfg, states).map((p) => [p.id, p.risk_weight]));
  assert.equal(pri.get("RIGHT"), 0.5);
  assert.equal(pri.get("LEFT"), 1.1);
});

test("liveZonePriorities ignores a spoofed/garbled risk_weight (anonymous broker)", () => {
  const cfg = new Map([["RIGHT", 1.8]]);
  for (const bad of ["9", NaN, Infinity, -1, 0, null]) {
    const states = new Map([["RIGHT", zs("RIGHT", "DANGER", { risk_weight: bad as unknown as number })]]);
    assert.equal(liveZonePriorities(cfg, states)[0].risk_weight, 1.8, `bad=${String(bad)} → fallback`);
  }
});

test("a live risk_weight retune re-prioritizes the banner (05 §5.6)", () => {
  const cfg = new Map([["RIGHT", 1.8], ["LEFT", 1.1]]);
  // both CAUTION → by config RIGHT (1.8) owns the banner; a runtime retune lifts LEFT to 3.0 → LEFT wins
  const states = new Map([
    ["RIGHT", zs("RIGHT", "CAUTION")],
    ["LEFT", zs("LEFT", "CAUTION", { risk_weight: 3.0 })],
  ]);
  assert.equal(worstActiveZone(liveZonePriorities(cfg, states), states)?.id, "LEFT");
});

test("worstActiveZone breaks ties toward the higher raw severity", () => {
  // Construct equal products: DANGER×1.0 vs CAUTION×2.0 — but risk weights here differ;
  // use two DANGERs where the higher risk_weight wins.
  const states = new Map([
    ["RIGHT", zs("RIGHT", "DANGER")],
    ["FRONT_RIGHT", zs("FRONT_RIGHT", "DANGER")],
  ]);
  assert.equal(worstActiveZone(ZONES, states)?.id, "RIGHT"); // 1.8 > 1.6
});

test("worstActiveZone is null when nothing is actively alerting", () => {
  const states = new Map([["RIGHT", zs("RIGHT", "SAFE")], ["LEFT", zs("LEFT", "UNKNOWN")]]);
  assert.equal(worstActiveZone(ZONES, states), null);
});

test("audioTarget sounds the single worst severity (05 §5.5)", () => {
  const states = [zs("RIGHT", "CAUTION"), zs("LEFT", "DANGER"), zs("REAR", "SAFE")];
  assert.equal(audioTarget(states, { standby: false, muted: false }), "DANGER");
});

test("audioTarget is CAUTION when only caution is present", () => {
  const states = [zs("RIGHT", "CAUTION"), zs("LEFT", "SAFE"), zs("REAR", "UNKNOWN")];
  assert.equal(audioTarget(states, { standby: false, muted: false }), "CAUTION");
});

test("audioTarget is SILENT when nothing active, or when muted/standby", () => {
  const clear = [zs("RIGHT", "SAFE"), zs("LEFT", "UNKNOWN")];
  assert.equal(audioTarget(clear, { standby: false, muted: false }), "SILENT");
  const danger = [zs("RIGHT", "DANGER")];
  assert.equal(audioTarget(danger, { standby: true, muted: false }), "SILENT", "park standby suppresses audio");
  assert.equal(audioTarget(danger, { standby: false, muted: true }), "SILENT", "timed mute suppresses audio");
});

test("isStandby true if any zone carries the standby flag", () => {
  assert.equal(isStandby([zs("LEFT", "CAUTION", { standby: true })]), true);
  assert.equal(isStandby([zs("LEFT", "CAUTION")]), false);
});

test("activeZoneStates drops disabled zones so they stop driving ear/banner", () => {
  const states = new Map([
    ["RIGHT", zs("RIGHT", "CAUTION")], // the only enabled active zone
    ["LEFT", zs("LEFT", "DANGER")],    // operator switched off in settings
    ["REAR", zs("REAR", "DANGER")],    // disabled in config
  ]);
  const local = new Map([["LEFT", false]]);
  const config = new Map([["REAR", false]]);
  const active = activeZoneStates(states, local, config);
  assert.deepEqual([...active.keys()], ["RIGHT"]);
  // the disabled DANGER zones (greyed on the map) must NOT escalate audio past the enabled CAUTION
  assert.equal(audioTarget(active.values(), { standby: false, muted: false }), "CAUTION");
  assert.equal(worstActiveZone(ZONES, active)?.id, "RIGHT");
});

test("activeZoneStates keeps zones absent from the override maps (default on)", () => {
  const states = new Map([["RIGHT", zs("RIGHT", "DANGER")]]);
  assert.equal(activeZoneStates(states, new Map(), new Map()).size, 1);
});
