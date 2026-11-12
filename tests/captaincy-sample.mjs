import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const sample = (n, cap) => ({ n, cap: {1: cap}, eo: {1: cap + 10}, own: {1: cap} });
function setup(crowd) {
  const team = {cap: 1, vice: 2, xi: [1,2], bench: [], moves0: [], later: [],
    week: {sq: [], bank: 0, over: []}, score: {tot: 10, ftLeft: 1, weeks: []}};
  const score = {tot: 10, ftLeft: 1, weeks: [{gw: 11, team, hits: 0}]};
  const ctx = vm.createContext({location: {hash: ''}, crowd,
    myTeam: () => team, scoreMoves: () => score, baseScore: () => score, mk: x => x,
    verdict: () => ({t:'Strong', c:'good'}), threats: () => [], vPill: () => '',
    term: (_, label) => label, MODES: {balanced:'Balanced'}, ftValue: () => 1.5,
    priceRising: () => false, priceFalling: () => false});   // plan.js is stubbed here; no player has a price projection
  for (const file of ['core/state', 'core/model', 'views/week', 'views/planner']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${file}.js`, import.meta.url), 'utf8'), ctx);
  }
  vm.runInContext(`D={crowd, meta:{next_gw:11}, manager:{free_transfers:1}, plans:{}, chips:[], lineup:{current_xi:[]}};
    P={1:{name:'Captain',pos:'GKP',team:1,xp:{11:5},nailed:90},2:{name:'Vice',pos:'MID',team:1,xp:{11:4}}};
    T={1:{fx:{11:[]}}}; GWS=PG=[11]; SB={moves:[]};`, ctx);
  return expression => vm.runInContext(expression, ctx);
}

for (const [name, crowd, key, label, pct] of [
  ['near', {gw:10, near:sample(100,71), top10k:sample(200,19)}, 'near', 'managers near your rank',71],
  ['fallback', {gw:10, near:sample(99,71), top10k:sample(200,19)}, 'top10k','the top 10k',19],
  ['near missing', {gw:10, top10k:sample(200,19)}, 'top10k','the top 10k',19],
]) test(`${name}: selected values and source labels stay together`, () => {
  const run=setup(crowd), c=run('weekCalls()');
  assert.equal(c.capEO,pct); assert.equal(c.capSample.key,key); assert.equal(c.capSample.label,label);
  assert.equal(c.capSample.gw,10); assert.equal(c.cV.tag, pct >= 50 ? "Field's pick" : null);
  assert.equal(run('fieldEO()[1]'),pct+10);
  assert.match(run('captainsHTML()'),new RegExp(`share of ${label} who captained him in GW10`));
  assert.ok(run('captainsHTML()').includes(`${pct}% field C`));
  assert.ok(run('whyIn(1, 11)').includes(`EO among ${label}`));
});

for (const [name,crowd] of [
  ['no crowd',null], ['no samples',{gw:10}],
  ['empty samples',{gw:10,near:sample(0,71),top10k:sample(0,19)}],
  ['too few near, no top',{gw:10,near:sample(99,71)}],
  ['missing maps',{gw:10,near:{n:100},top10k:{n:200}}],
]) test(`${name}: no invented ownership or captaincy percentage`, () => {
  const run=setup(crowd), c=run('weekCalls()');
  assert.equal(c.capEO,null); assert.equal(c.capSample,null); assert.equal(c.cV.tag,null);
  assert.equal(run('fieldEO()'),null);
  const html=run('captainsHTML()');
  assert.match(html,/Captaincy sample unavailable/); assert.doesNotMatch(html, /% field C/);
});

test('real zero captaincy remains 0% within an available sample', () => {
  const run=setup({gw:10,near:sample(100,0),top10k:sample(200,19)});
  assert.equal(run('weekCalls().capEO'),0);
  assert.match(run('captainsHTML()'),/0% field C/);
  assert.doesNotMatch(run('captainsHTML()'),/sample unavailable/);
});
