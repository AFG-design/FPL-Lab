// FL-124: two ARIA patterns. (1) An AFG row's <summary> is the row's toggle, so it holds no other control: the player
// sheet opens from a button in the expanded row. (2) The Planner's view tabs are a real tablist, as Home's are:
// aria-selected (never aria-pressed, which is for toggle buttons), one tab in the Tab order, and a tabpanel they
// control. Tap target sizes need a browser: scripts/tap_check.py checks those on the Check site workflow.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function app() {
  const positions = ["GKP", "GKP", ...Array(5).fill("DEF"), ...Array(5).fill("MID"), ...Array(3).fill("FWD")];
  const players = positions.map((pos, i) => ({ id: i + 1, name: "Player " + (i + 1), pos, team: i + 1, price: 5, ok: true,
    nailed: 100, status: "a", dist: {}, xp: { 10: 4, 11: 4 } }));
  const local = new Map();
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout, players, addEventListener: () => {}, matchMedia: () => ({ matches: false, addEventListener: () => {} }),
    localStorage: { getItem: k => local.get(k) ?? null, setItem: (k, v) => local.set(k, v) },
    document: { querySelectorAll: () => [], querySelector: () => null, addEventListener: () => {}, getElementById: () => null } });
  for (const f of ["core/state", "core/model", "core/plan", "components/ui", "components/explain", "views/tpaths",
    "views/planner", "views/planner-views", "views/afg"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + f + ".js", import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`
    syncPush = () => {}; render = () => {};
    const wk = gw => ({ gw, in: [], out: [], xi: [], bench: [], captain: 0 });
    D = { players, meta: { team_id: 1, next_gw: 10, built: "t" }, squad: players.map(p => ({ id: p.id, sell: 5, buy: 5 })),
      manager: { bank: 0, free_transfers: 1 }, crowd: null, fixtures: [], plan_rules: {},
      teams: Object.fromEntries(players.map(p => [p.team, { short: "T" + p.team, name: "Team " + p.team, fx: {} }])),
      plans: { roll: { vs_roll: 0, weeks: [wk(10), wk(11)] } },
      afg: { p: { 1: { x: 4.6, n: 0.6, why: [["venue", 0.6, "Strong home record"]] } } } };
    P = Object.fromEntries(players.map(p => [p.id, p])); T = D.teams; GWS = PG = [10, 11];
    S.mode = "balanced"; SB = null; loadSandbox();
    // the Planner's tab bodies aren't under test here: only the tabs and the panel that wraps them
    pvMine = pvStrategy = vTpaths = plannerEditor = () => "<p>body</p>";
  `, ctx);
  return expr => vm.runInContext(expr, ctx);
}

test("an AFG row's summary holds no control; the player button is in the expanded row", () => {
  const html = app()("afgRow(1, 10)");
  const summary = html.match(/<summary>([\s\S]*?)<\/summary>/)[1];
  assert.doesNotMatch(summary, /<(button|a|select|input)\b/, "no control inside <summary>");
  assert.match(html.split("</summary>")[1], /<button[^>]*data-p="1"[^>]*>Player 1: player details<\/button>/);
});

for (const view of ["mine", "suggest", "compare", "edit"]) {
  test(`Planner tabs are a tablist with ${view} selected: aria-selected, one tab in the Tab order, a tabpanel`, () => {
    const run = app();
    run(`S.pview = ${JSON.stringify(view)}`);
    const tabs = [...run("pvTabs()").matchAll(/<button[^>]*role="tab"[^>]*>/g)].map(m => m[0]);
    assert.ok(tabs.length >= 4);
    for (const t of tabs) {
      assert.doesNotMatch(t, /aria-pressed/, "tabs carry aria-selected, not aria-pressed");
      assert.match(t, /aria-controls="pvpanel"/);
    }
    const on = tabs.filter(t => /aria-selected="true"/.test(t));
    assert.equal(on.length, 1);
    assert.match(on[0], new RegExp(`id="pvtab-${view}"[^>]*tabindex="0"`));
    assert.equal(tabs.filter(t => /tabindex="0"/.test(t)).length, 1, "only the selected tab is in the Tab order");
    assert.match(run("vPlanner()"), new RegExp(`<div id="pvpanel" role="tabpanel" aria-labelledby="pvtab-${view}">`));
  });
}
