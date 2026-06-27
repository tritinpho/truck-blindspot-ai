// L2-equivalent for the wire-input trust boundary (06 §6.5). Pure logic. Run: node --test
import { test } from "node:test";
import assert from "node:assert/strict";
import { isRenderableRange, isRenderableZone, zoneSchemaMajorOk } from "../src/validate.ts";

test("isRenderableRange accepts finite numbers and null/absent, rejects wrong types", () => {
  for (const ok of [0, 1.23, -1, 1000, null, undefined]) {
    assert.equal(isRenderableRange(ok), true, `${String(ok)} should be renderable`);
  }
  // a string/array/bool/NaN/Inf would all break `.toFixed()` in the banner/scene
  for (const bad of ["1.2", "x", [1], {}, true, NaN, Infinity]) {
    assert.equal(isRenderableRange(bad), false, `${String(bad)} should be rejected`);
  }
});

test("isRenderableZone rejects a spoofed/skewed nearest_range_m before it reaches .toFixed()", () => {
  const base = { schema: "bsw.zone_state/1", zone_id: "RIGHT", ts: 0, severity: "DANGER" };
  assert.equal(isRenderableZone({ ...base, nearest_range_m: 1.2 }), true);
  assert.equal(isRenderableZone({ ...base, nearest_range_m: null }), true); // stale-hold: DANGER w/ null range is legit
  assert.equal(isRenderableZone({ ...base }), true);                        // range absent
  assert.equal(isRenderableZone({ ...base, nearest_range_m: "1.2" }), false); // the exact freeze trigger
  assert.equal(isRenderableZone({ ...base, nearest_range_m: [1] }), false);
});

test("zoneSchemaMajorOk rejects only a recognised-but-incompatible major (04 §4.4)", () => {
  assert.equal(zoneSchemaMajorOk("bsw.zone_state/1"), true);
  assert.equal(zoneSchemaMajorOk("bsw.zone_state/2"), false); // breaking major → drop
  assert.equal(zoneSchemaMajorOk(undefined), true);           // absent envelope → field checks decide
  assert.equal(zoneSchemaMajorOk("something-else"), true);    // unparseable → don't over-reject
});

test("isRenderableZone drops an incompatible zone_state major, ages zone to UNKNOWN (fail-loud)", () => {
  const base = { zone_id: "RIGHT", ts: 0, severity: "DANGER", nearest_range_m: 1.2 };
  assert.equal(isRenderableZone({ ...base, schema: "bsw.zone_state/1" }), true);
  assert.equal(isRenderableZone({ ...base, schema: "bsw.zone_state/2" }), false); // v2 → not rendered
  assert.equal(isRenderableZone({ ...base }), true); // schema absent → still renders on valid fields
});

test("isRenderableZone still rejects unknown severity and missing/empty zone_id", () => {
  assert.equal(isRenderableZone({ zone_id: "RIGHT", severity: "BOOM" }), false); // not in SEVERITY
  assert.equal(isRenderableZone({ zone_id: "", severity: "SAFE" }), false);
  assert.equal(isRenderableZone({ severity: "SAFE" }), false);
  assert.equal(isRenderableZone(null), false);
  assert.equal(isRenderableZone(42), false); // a bare primitive must not throw or pass
});
