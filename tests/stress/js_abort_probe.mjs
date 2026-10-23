import fs from "node:fs"; import path from "node:path"; import { createRequire } from "node:module";
const require = createRequire("/home/claude/fpl-lab/tests/stress/x.mjs"); const ROOT="/home/claude/fpl-lab";
const S = require(ROOT+"/site/plan-solver.js"); const H = require(ROOT+"/site/vendor/highs.js");
const d = JSON.parse(fs.readFileSync("/home/claude/fpl-lab/tests/stress/out/_js_solver_in.json"));
const c = d.cases.find(x=>x.name==="chase_ft2");
const inp = {...c.opts, players:d.players, squad:c.squad, sell:c.sell, bank:c.bank, ft0:c.ft0, gws:c.gws};
const {lp} = S.buildLP(inp);
for (const o of [{mip_rel_gap:0.001,time_limit:25,presolve:"on"},{mip_rel_gap:0.001,time_limit:25,presolve:"off"},{mip_rel_gap:0.01,time_limit:25,presolve:"on"},{mip_rel_gap:0,time_limit:25,presolve:"on"},{mip_rel_gap:0.001,time_limit:25,presolve:"on",random_seed:7}]) {
  const h = await H({locateFile:f=>ROOT+"/site/vendor/"+f}); const t=Date.now();
  try { const s=h.solve(lp,o); console.log(JSON.stringify(o), s.Status, s.ObjectiveValue, (Date.now()-t)/1000);} catch(e){console.log(JSON.stringify(o),"ERR",String(e.message).slice(0,80),(Date.now()-t)/1000)}
}
