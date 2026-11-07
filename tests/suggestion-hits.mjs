// Run the Planner's actual suggestion engine with a small, deterministic transfer market.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function planner(mode, spare = false, pair = false, horizon = 2) {
  const ctx = vm.createContext({ location: { hash: "" } });
  for (const file of ["core/state", "core/model", "core/plan", "views/planner"]) {
    vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  }
  const positions = ["DEF", "MID", "FWD", "GKP", "DEF", "MID", "FWD", "GKP"];
  const players = positions.map((pos, i) => ({
    id: i + 1, pos, team: i + 1, name: String(i + 1), price: 5,
    xp: { 10: i === 4 ? 15 : 1, 11: i === 4 ? 15 : 1 },
  }));
  // In the pair case the upgrade costs £1m more and a keeper sale funds it.
  if (pair) { players[4].price++; players[7].price--; }
  Object.assign(ctx, { players, mode, spare, pair, horizon });
  vm.runInContext(`
    function term(key, label) { return label; }
    function blankChip() { return ""; }
    T = Object.fromEntries(players.map(p => [p.team, { short: "CLB", fx: {} }]));
    S.mode = mode; GWS = [10, 11]; PG = GWS.slice(0, horizon);
    D = { players, meta: { built: "fixture" }, squad: players.slice(0,4).map(p => ({ id: p.id, sell: 5 })),
          manager: { bank: 0, free_transfers: (pair ? 2 : 1) + Number(spare) } };
    P = Object.fromEntries(players.map(p => [p.id, p]));
    SB = { moves: [{ gw: 11, out: 2, in: 6 }, { gw: 11, out: 3, in: 7 }],
           rules: { locked: [2,3], banned: [] }, ov: {} };
  `, ctx);
  return expr => vm.runInContext(expr, ctx);
}

for (const pair of [false, true]) {
  const kind = pair ? "pair" : "single";
  const list = pair ? "pairSuggestions(10)" : "transferSuggestions(10)";
  for (const mode of ["balanced", "safe"]) {
    test(kind + " in " + mode + " cannot spend GW11's rolled transfer", () => {
      assert.equal(planner(mode, false, pair)(list + ".length"), 0);
      assert.equal(planner(mode, false, pair, 1)(list + ".length"), 0);
    });
    test(kind + " in " + mode + " can use a spare free transfer", () => {
      assert.ok(planner(mode, true, pair)(list + ".length") > 0);
    });
  }
  test(kind + " in Chase shows the GW11 cost on a GW10 suggestion", () => {
    const run = planner("chase", false, pair);
    const html = run(pair ? "pairsHTML(10)" : "suggestionsHTML(10)");
    assert.match(html, /class="pill bad">GW11 · −4 hit/);
    assert.doesNotMatch(html, /class="pill bad">GW10/);
  });
}
