// Use the Python scorer's totals and multipliers to check the actual pitch-rendering path.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const fixtures = JSON.parse(execFileSync("python3", ["-c", `
import json
import fpl_score as f
pos = {i + 1: p for i, p in enumerate(["GKP"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2 + ["GKP", "DEF", "MID", "FWD"])}
team = dict(xi=list(range(1, 12)), bench=list(range(12, 16)), captain=10, vice=6, pos=pos)
xp = {i: 5 if i == 10 else 2 for i in pos}
rows = []
for chip in (None, "3xc"):
    for absent in (False, True):
        played = {i: (0, 0) if i == 10 and absent else (90, x) for i, x in xp.items()}
        actual = f.score_team(team, played, chip)
        side = dict(xi=team["xi"], bench=team["bench"], cap=10, vice=6, armband=actual["captain"],
                    subs=actual["subs"], pts=actual["total"], formation="4-4-2", captain_multiplier=actual["captain_multiplier"])
        for basis in ("suggested", "your 15"):
            if basis == "suggested":
                suggestion = f.best_suggestion({"best": {"weeks": [dict(gw=10, xi=team["xi"], captain=10,
                    xp=f.expected(team, xp), hits=0)]}}, 10)
                target = dict(suggestion, basis=basis, xi_xp=xp, xi_pts={i: p[1] for i, p in played.items()}, actual=0)
            else:
                target = dict(basis=basis, assumed=True, exp=f.expected(team, xp, chip), captain_multiplier=f.captain_multiplier(chip))
            target["par"] = f.target(target["exp"])
            rows.append(dict(gw=10, chip=chip, absent=absent, xp=xp, pts={i: p[1] for i, p in played.items()},
                target=target, you=side, model=side, hits=0, you_net=actual["total"], fpl_pts=actual["total"], res=f.result(actual["total"], target["par"])))
print(json.dumps(rows))
`], { encoding: "utf8" }));

function render(w) {
  const pitches = [];
  const ctx = vm.createContext({ location: { hash: "" }, w, pitches,
    luPitch: (xi, bench) => { pitches.push({ xi, bench }); return "<pitch></pitch>"; } });
  for (const file of ["core/state", "views/vsmodel"]) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), "utf8"), ctx);
  }
  vm.runInContext(`P = Object.fromEntries(Object.keys(w.xp).map(i => [i, { name: 'Player ' + i }]));
    const PLAN_LABEL = { best: 'Best' };`, ctx);
  return { html: vm.runInContext("vmWeek(w)", ctx), pitches };
}

for (const fixture of fixtures) {
  for (const legacy of [false, true]) {
    test(`${fixture.chip || "normal"}, ${fixture.target.basis}, ${fixture.absent ? "vice inherits" : "captain plays"}, ${legacy ? "cached" : "new"} build: pitch totals match`, () => {
      const w = structuredClone(fixture);
      if (legacy) {
        delete w.target.captain_multiplier;
        delete w.you.captain_multiplier;
        delete w.model.captain_multiplier;
      }
      const { html, pitches: [you, model] } = render(w);
      const sum = items => items.reduce((n, p) => n + Number(p.big), 0);
      const counted = [...you.xi, ...you.bench].filter(p => p.cls !== "lvc-nocount");
      assert.equal(sum(counted) - w.hits, w.you_net);
      assert.equal(sum(model.xi) - 4 * (w.target.hits || 0), w.target.exp);
      assert.equal(Math.round(sum(model.xi)), w.target.par);
      const mult = fixture.target.captain_multiplier;
      assert.equal(Number(model.xi.find(p => p.id === 10).big), 5 * mult);
      assert.match(html, new RegExp(`captain ×${mult} included`));
      assert.ok(html.includes(`<b>${w.target.par}</b>`));
      assert.ok(html.includes(`<b>${w.you_net}</b>`));
      assert.equal(counted.find(p => p.id === w.you.armband).c.x2, `C ×${w.chip === "3xc" ? 3 : 2}`);
    });
  }
}
