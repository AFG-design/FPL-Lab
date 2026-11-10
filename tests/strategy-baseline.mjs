// FL-076: switching strategy must refresh the cached keep-squad baseline (_base in core/plan.js), so the Planner's
// "vs no transfers" and "if you do nothing" match a fresh load in the new strategy. Drives the real [data-mode]
// handler in shell/events.js, for a hand-edited plan and for a plan picked from the options.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function app() {
  const positions = ["GKP", "GKP", ...Array(5).fill("DEF"), ...Array(5).fill("MID"), ...Array(3).fill("FWD"), "MID"];
  // 8 is the best projected captain; 9 projects less but has a big haul chance, so Chase rank captains him and the
  // no-transfers baseline is lower in Chase than in Balanced / Play safe. 16 is a signing for the hand-edited plan.
  const players = positions.map((pos, i) => ({
    id: i + 1, pos, team: i + 1, price: 5, ok: true, nailed: 100,
    xp: { 10: i === 7 ? 8 : i === 8 ? 6 : i === 15 ? 7 : 4, 11: i === 7 ? 8 : i === 8 ? 6 : i === 15 ? 7 : 4 },
    dist: i === 8 ? { 10: [0.6], 11: [0.6] } : {},
  }));
  const buttons = ["balanced", "safe", "chase"].map(mode => ({ dataset: { mode } }));
  const local = new Map();
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout, players, buttons,
    localStorage: { getItem: k => local.get(k) ?? null, setItem: (k, v) => local.set(k, v) },
    document: { querySelectorAll: sel => sel === "[data-mode]" ? buttons : [], querySelector: () => null } });
  for (const file of ["core/state", "core/model", "core/plan", "views/tpaths", "views/planner", "views/planner-views", "shell/events"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`
    syncPush = () => {}; render = () => {};
    // other views' binders: not under test here (only their buttons would be bound, and none are on this fake page)
    bindHome = bindXp = bindTpaths = bindTpEdit = bindPlannerViews = bindStatsMore = () => {};
    D = { players, meta: { team_id: 1, next_gw: 10 }, squad: players.slice(0, 15).map(p => ({ id: p.id, sell: 5, buy: 5 })),
      manager: { bank: 0, free_transfers: 1 }, crowd: null,
      plans: { roll: { vs_roll: 0, weeks: [{ gw: 10, in: [], out: [], xi: [], bench: [], captain: 0 }, { gw: 11, in: [], out: [], xi: [], bench: [], captain: 0 }] },
               one: { vs_roll: 3, weeks: [{ gw: 10, in: [16], out: [12], xi: [], bench: [], captain: 0 }, { gw: 11, in: [], out: [], xi: [], bench: [], captain: 0 }] } } };
    // plans carry no lineup here (empty xi), so planScore picks the best XI itself, marked filled
    P = Object.fromEntries(players.map(p => [p.id, p]));
    T = Object.fromEntries(players.map(p => [p.team, { short: "T" + p.team }]));
    GWS = PG = [10, 11];
    S.mode = "balanced"; SB = null; loadSandbox();
  `, ctx);
  const run = expr => vm.runInContext(expr, ctx);
  run("bind()");
  // what the Planner shows (plannerEditor: delta = tot - baseTot, "baseTot if you do nothing") ...
  const shown = () => JSON.parse(run(`(() => { const s = sandboxSummary(); return JSON.stringify({ mode: S.mode, vs: s.tot - s.baseTot, base: s.baseTot }); })()`));
  // ... and what a fresh load of the same plan and strategy shows: no cached baseline
  const fresh = () => JSON.parse(run(`(() => { _base = null; const s = sandboxSummary(); return JSON.stringify({ mode: S.mode, vs: s.tot - s.baseTot, base: s.baseTot }); })()`));
  const click = mode => { buttons.find(b => b.dataset.mode === mode).onclick(); };
  return { run, shown, fresh, click };
}

const SEQ = ["chase", "safe", "balanced", "chase"];

test("hand-edited plan: switching strategy refreshes vs no transfers and if you do nothing", () => {
  const a = app();
  a.run(`editPlan(() => { SB.moves = [{ gw: 10, out: 12, in: 16 }]; })`);
  assert.equal(a.run("SB.source"), "custom");
  a.shown();   // fill the cache in Balanced, as rendering the page does
  const bases = new Set();
  for (const mode of SEQ) {
    a.click(mode);
    const s = a.shown();
    assert.equal(s.mode, mode);
    assert.deepEqual(s, a.fresh(), `${mode}: shown figures match a fresh load`);
    bases.add(s.base.toFixed(2));
  }
  assert.ok(bases.size > 1, "the baseline differs between strategies, so a stale one would show");
});

test("plan picked from the options: switching strategy refreshes vs no transfers and if you do nothing", () => {
  const a = app();
  a.run(`useModelPlan("one", "balanced")`);
  assert.equal(a.run("SB.source"), "plan:one");
  a.shown();
  const bases = new Set();
  for (const mode of SEQ) {
    a.click(mode);
    const s = a.shown();
    assert.equal(s.mode, mode);
    assert.deepEqual(s, a.fresh(), `${mode}: shown figures match a fresh load`);
    bases.add(s.base.toFixed(2));
  }
  assert.ok(bases.size > 1, "the baseline differs between strategies, so a stale one would show");
});
