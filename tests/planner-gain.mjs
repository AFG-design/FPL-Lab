// FL-125: the Planner shows one "vs no transfers" figure, the same as data.json's plans[*].vs_none: projected points
// after hits plus plan_rules.ft_value for each free transfer banked at the end, against keeping the squad. Before,
// the strategy tab, its KPI, the option cards and Compare showed points only (Balanced +7.4 where data.json had
// +5.88 on 12 Nov), because a plan that spends a transfer banks one fewer than doing nothing.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function app(rules) {
  const positions = ["GKP", "GKP", ...Array(5).fill("DEF"), ...Array(5).fill("MID"), ...Array(3).fill("FWD"), "MID"];
  // 16 (not in the squad) projects 7 a week against 12's 4: one transfer, 12 -> 16, gains 3 points a week
  const players = positions.map((pos, i) => ({
    id: i + 1, pos, team: i + 1, price: 5, ok: true, nailed: 100, dist: {},
    xp: { 10: i === 15 ? 7 : 4, 11: i === 15 ? 7 : 4 },
  }));
  const local = new Map();
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout, players, rules,
    localStorage: { getItem: k => local.get(k) ?? null, setItem: (k, v) => local.set(k, v) },
    document: { querySelectorAll: () => [], querySelector: () => null } });
  for (const file of ["core/state", "core/model", "core/plan", "views/tpaths", "views/planner", "views/planner-views"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`
    syncPush = () => {}; render = () => {};
    const wk = (gw, i, o) => ({ gw, in: i, out: o, xi: [], bench: [], captain: 0 });
    D = { players, meta: { team_id: 1, next_gw: 10, built: "t" }, squad: players.slice(0, 15).map(p => ({ id: p.id, sell: 5, buy: 5 })),
      manager: { bank: 0, free_transfers: 1 }, crowd: null, plan_rules: rules,
      plans: { roll: { vs_roll: 0, weeks: [wk(10, [], []), wk(11, [], [])] },
               one: { vs_roll: 3, weeks: [wk(10, [16], [12]), wk(11, [], [])] } } };
    P = Object.fromEntries(players.map(p => [p.id, p]));
    T = Object.fromEntries(players.map(p => [p.team, { short: "T" + p.team }]));
    GWS = PG = [10, 11];
    S.mode = "balanced"; SB = null; loadSandbox();
  `, ctx);
  return expr => vm.runInContext(expr, ctx);
}

for (const ftv of [1.5, 2]) {
  test(`strategy tab, Compare, drafts and Your plan show the same vs_none figure (ft_value ${ftv})`, () => {
    const run = app({ ft_value: ftv, tie: 0.1, min_profit: 1, strategy: {} });
    const r = JSON.parse(run(`(() => { const r = pvStrat("balanced"), b = pvBase();
      return JSON.stringify({ key: r.key, gain: r.gain, pts: r.sc.tot - b.tot, ft: r.sc.ftLeft, bft: b.ftLeft }); })()`));
    assert.equal(r.key, "one");
    assert.equal(r.ft, r.bft - 1, "the plan spends the free transfer that doing nothing banks");
    // 16 starts and captains: (7 - 4) x 2 = 6 a week over two weeks, less one banked FT
    assert.ok(Math.abs(r.pts - 12) < 1e-9, `points gain ${r.pts}`);
    assert.ok(Math.abs(r.gain - (12 - ftv)) < 1e-9, `shown gain ${r.gain}`);
    // the same plan, made Your plan: KPI, drafts and the vs-no-transfers panel agree with the tab
    run(`useModelPlan("one", "balanced")`);
    const s = JSON.parse(run(`JSON.stringify({ sum: sandboxSummary().gain,
      draft: draftSummary({ name: "x", moves: SB.moves, ov: SB.ov, mode: S.mode, solved: SB.solved }).gain })`));
    assert.ok(Math.abs(s.sum - r.gain) < 1e-9, `sandbox ${s.sum}`);
    assert.ok(Math.abs(s.draft - r.gain) < 1e-9, `draft ${s.draft}`);
    assert.match(run("vsCurrentTeam()"), new RegExp(`vs no transfers</h3><b[^>]*>\\+${(12 - ftv).toFixed(1)}<`));
  });
}

test("the strategy tab is labelled as vs no transfers", () => {
  const run = app({ ft_value: 1.5, tie: 0.1, strategy: {} });
  const html = run("pvTabs()");
  assert.match(html, /title="vs no transfers over 2 GWs, after hits, with each free transfer banked at the end worth 1\.5">Balanced \+10\.5</);
});
