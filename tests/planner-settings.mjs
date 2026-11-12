// FL-075: the browser solver reads the server's planner settings (data.json plan_rules, optimise.planner_settings)
// instead of its own copies, so Re-plan solves the same problem as the server's plans. Before, it used a smaller
// shortlist (82 players, not 124), ownership for 2 weeks (not the whole plan) and its own variance formula, and could
// find a worse plan than the server's Balanced one (1.2-5.1 points over 5 GWs on test squads).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import makeHighs from "../site/vendor/highs.js";
import solver from "../site/plan-solver.js";

const highs = await makeHighs();
const RULES = JSON.parse(readFileSync(new URL("./fixtures/plan_rules.json", import.meta.url), "utf8"));

// A seeded synthetic league: 20 clubs, 200 players, 5 gameweeks; the squad is a cheap, weak 15. The same case goes to
// optimise.solve (CBC) and to plan-solver.js (HiGHS); both must reach the same plan value.
const PY = `
import json, random, sys
import optimise
rng = random.Random(7)
pos = ["GKP"] * 24 + ["DEF"] * 64 + ["MID"] * 70 + ["FWD"] * 42
gws = [11, 12, 13, 14, 15]
players = {}
for k, p in enumerate(pos, start=1):
    base = rng.uniform(1.0, 6.5)
    players[k] = {"pos": p, "team": 1 + k % 20, "price": round(4.0 + base * 1.2 + rng.uniform(-0.5, 0.5), 1),
                  "xp": {g: round(max(0.0, base + rng.uniform(-1.5, 1.5)), 2) for g in gws}, "ok": True,
                  "p10": {g: round(min(0.4, base / 20), 3) for g in gws}, "nailed": 100}
squad = [1, 2] + [25 + i for i in range(5)] + [89 + i for i in range(5)] + [159 + i for i in range(3)]
for i in squad:
    players[i]["xp"] = {g: 1.0 for g in gws}
    players[i]["price"] = 4.5
eo = {i: round(rng.uniform(0, 0.6), 3) for i in players}
mode = sys.argv[1]
st = {} if mode == "balanced" else dict(optimise.STRATEGY[mode], eo=eo, eo_weeks=optimise.EO_WEEKS or len(gws))
r = optimise.solve(players, squad, {}, 2.0, 1, gws, max_hits=0, time_limit=60, **st)
print(json.dumps({"players": {str(k): v for k, v in players.items()}, "squad": squad, "gws": gws, "eo": eo,
                  "value": r["value"], "moves": sum(len(w["in"]) for w in r["weeks"])}))
`;

for (const mode of ["balanced", "chase"]) {
  test(`${mode}: the browser solver reaches the server's plan value with the shipped settings`, async () => {
    const py = JSON.parse(execFileSync("python3", ["-c", PY, mode], { encoding: "utf8", cwd: new URL("..", import.meta.url).pathname }));
    const players = Object.fromEntries(Object.entries(py.players).map(([k, v]) => [+k, v]));
    const st = RULES.strategy[mode] || {};
    const inp = { players, squad: py.squad, sell: {}, bank: 2.0, ft0: 1, gws: py.gws, maxHits: 0,
      ...solver.settingsFrom(RULES),
      ...(mode === "balanced" ? {} : { eo: py.eo, lam: st.lam, haulW: st.haul_w || 0, nailW: st.nail_w || 0, hitMargin: st.hit_margin || 0 }) };
    const r = await solver.solve(highs, inp);
    // both solvers stop at a 0.1% gap: allow that much of the plan's value
    assert.ok(Math.abs(r.value - py.value) <= 0.002 * py.value, `browser ${r.value.toFixed(2)} v server ${py.value.toFixed(2)}`);
  });
}

test("settings come from plan_rules, and a data.json without them is refused, not guessed", () => {
  const s = solver.settingsFrom(RULES);
  assert.deepEqual({ ...s.pool }, { ...RULES.pool });
  assert.equal(s.eoWeeks, RULES.eo_weeks);
  assert.equal(solver.settingsFrom({ ...RULES, pool: undefined }), null);
  assert.equal(solver.settingsFrom(null), null);
  assert.throws(() => solver.buildLP({ players: {}, squad: [], gws: [11] }), /planner settings missing/);
});
