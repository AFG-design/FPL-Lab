// FL-164: when the captain call is a Coin flip, the card leads with what does differ between the options: each one's
// projected chance of 10+ points (haulChance) and how a mini-league's managers captained in the sampled GW
// (leagueCaptains, actual picks). Missing data is said, never shown as 0%.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const ctx = vm.createContext({ localStorage: { getItem: () => null, setItem: () => {} }, location: { hash: "" } });
for (const f of ["core/state", "core/model"]) vm.runInContext(readFileSync(new URL(`../site/js/${f}.js`, import.meta.url), "utf8"), ctx);
vm.runInContext(`P = { 1: { name: "A", dist: { 11: [0.124, 0.4, 0.5] } }, 2: { name: "B", dist: { 11: [0.083] } }, 3: { name: "C" }, 4: { name: "D", dist: { 11: [0] } } };`, ctx);
const run = s => vm.runInContext(s, ctx);

test("chance of 10+ comes from the simulated distribution; missing is null and says so, a real 0 stays 0%", () => {
  assert.equal(run("haulChance(1, 11)"), 0.124);
  assert.equal(run("haulChance(3, 11)"), null);         // no distribution
  assert.equal(run("haulChance(1, 12)"), null);         // no distribution for that GW
  assert.equal(run("pctTxt(haulChance(1, 11))"), "12%");
  assert.equal(run("pctTxt(haulChance(3, 11))"), "no projection");
  assert.equal(run("pctTxt(haulChance(4, 11))"), "0%");
});

test("league captains: counts the armband (x2 or x3), leaves you out, names the most popular", () => {
  const lg = { rows: [
    { me: true, picks: [[1, 2], [2, 1]] },                // you: not counted
    { picks: [[1, 2], [2, 1]] }, { picks: [[1, 3], [2, 1]] },   // Triple Captain counts as captaining him
    { picks: [[2, 2], [1, 1]] }, { picks: [[9, 2], [1, 1]] }, { picks: [[9, 2]] }, { picks: [[9, 2]] },
    { picks: null },                                     // no picks in this update: not counted
  ] };
  const r = JSON.parse(JSON.stringify(run(`leagueCaptains(${JSON.stringify(lg)}, [1, 2])`)));
  assert.deepEqual(r, { n: 6, of: [{ id: 1, k: 2 }, { id: 2, k: 1 }], top: { id: 9, k: 3 } });
});

test("a tie for most popular is ambiguous: Home names an outsider only when he beat both options", () => {
  const home = readFileSync(new URL("../site/js/views/home.js", import.meta.url), "utf8");
  assert.match(home, /lc\.of\.every\(o => lc\.top\.k > o\.k\)/);
});

test("no league or no picks: null, so the card says the sample is unavailable", () => {
  assert.equal(run("leagueCaptains(null, [1, 2])"), null);
  assert.equal(run("leagueCaptains({ rows: [{ me: true, picks: [[1, 2]] }, { picks: null }] }, [1, 2])"), null);
});

test("Home and the Planner show the lead only on a Coin flip, with the projected / actual labels", () => {
  const home = readFileSync(new URL("../site/js/views/home.js", import.meta.url), "utf8");
  const plan = readFileSync(new URL("../site/js/views/planner.js", import.meta.url), "utf8");
  assert.match(home, /c\.cV\.t === "Coin flip"/);
  assert.match(home, /Chance of 10\+ points in GW\$\{g\} \(projected\)/);
  assert.match(home, /\(actual picks\)/);
  assert.match(home, /No mini-league sample yet/);
  assert.match(plan, /conf\.t === "Coin flip"/);
  assert.match(plan, /Chance of 10\+ \(projected\)/);
});
