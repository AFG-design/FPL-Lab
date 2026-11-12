// FL-075: the browser solver takes its settings from data.json plan_rules (optimise.planner_settings) and refuses
// without them. The server/browser parity check is tests/parity/planner-parity.mjs, run by test_planner_parity.py.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import solver from "../site/plan-solver.js";

const RULES = JSON.parse(readFileSync(new URL("./fixtures/plan_rules.json", import.meta.url), "utf8"));

test("settings come from plan_rules, and a data.json without them is refused, not guessed", () => {
  const s = solver.settingsFrom(RULES);
  assert.deepEqual({ ...s.pool }, { ...RULES.pool });
  assert.equal(s.eoWeeks, RULES.eo_weeks);
  assert.equal(solver.settingsFrom({ ...RULES, pool: undefined }), null);
  assert.equal(solver.settingsFrom(null), null);
  assert.throws(() => solver.buildLP({ players: {}, squad: [], gws: [11] }), /planner settings missing/);
});
