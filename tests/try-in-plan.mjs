// FL-156 (idea 7): Try in my plan. The preview works on a copy (the plan, saved paths and undo untouched until Apply),
// Apply goes through the Planner's edit + undo and matches the preview, eligibility follows money and the club limit,
// a later move made impossible is listed, and FTs / hits / chips follow the Planner's own scoring.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup() {
  const mem = {};
  const el = () => ({ innerHTML: '', open: false, value: '', disabled: false, showModal() { this.open = true; }, close() { this.open = false; },
    setAttribute() {}, removeAttribute() {}, addEventListener() {}, focus() {}, querySelector: () => null });
  const els = {};
  const ctx = vm.createContext({ location: { hash: '' }, setTimeout, matchMedia: () => ({ matches: false }),
    localStorage: { getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = v; } },
    document: { querySelector: s => (els[s] = els[s] || el()), querySelectorAll: () => [] } });
  for (const f of ['core/state', 'core/model', 'core/plan', 'components/ui', 'components/tags', 'components/watchlist', 'components/player-sheet']) {
    vm.runInContext(readFileSync(new URL(`../site/js/${f}.js`, import.meta.url), 'utf8'), ctx);
  }
  // 15 owned at £5m on 2 xP (club k+1), the 2nd keeper and 3 subs on 1; 16 a £6m MID on 6 xP (club 16); 17 a £5m MID of club 9
  vm.runInContext(`
    const pos = ["GKP","GKP","DEF","DEF","DEF","DEF","DEF","MID","MID","MID","MID","MID","FWD","FWD","FWD"];
    const list = pos.map((p, k) => ({ id: k + 1, name: "P" + (k + 1), pos: p, team: k + 1, price: 5, ok: true, status: "a",
      xp: { 11: [1,6,11,14].includes(k) ? 1 : 2, 12: [1,6,11,14].includes(k) ? 1 : 2, 13: [1,6,11,14].includes(k) ? 1 : 2 } }));
    list.push({ id: 16, name: "Star", pos: "MID", team: 16, price: 6, ok: true, status: "a", xp: { 11: 6, 12: 6, 13: 6 } });
    list.push({ id: 17, name: "Other", pos: "MID", team: 9, price: 5, ok: true, status: "a", xp: { 11: 3, 12: 3, 13: 3 } });
    list.push({ id: 18, name: "Def", pos: "DEF", team: 18, price: 5, ok: true, status: "a", xp: { 11: 3, 12: 3, 13: 3 } });
    D = { players: list, squad: list.slice(0, 15).map(p => ({ id: p.id, sell: p.id === 12 ? 5.4 : 5 })), manager: { bank: 0.7, free_transfers: 1 },
      plan_rules: { ft_value: 1.5 }, meta: { next_gw: 11, team_id: 1 }, chips: [{ key: "freehit", available: true, from: 2, to: 19 }], crowd: null };
    P = Object.fromEntries(list.map(p => [p.id, p])); MINE = new Set(list.slice(0, 15).map(p => p.id));
    T = Object.fromEntries(Array.from({ length: 20 }, (_, k) => [k + 1, { id: k + 1, short: "C" + (k + 1), name: "Club " + (k + 1), fx: {} }]));
    GWS = PG = [11, 12, 13];
    SB = { rules: { locked: [], banned: [] }, ov: {}, moves: [], chips: {}, solved: null, source: "custom", gw: 11, prev: null };
    toast = () => {}; render = () => {}; saveSandbox = () => {}; syncPush = () => {}; tpEditing = () => null; tpEditInfo = () => null;
    playerTags = () => ""; term = (k, t) => t;`, ctx);
  return { run: e => vm.runInContext(e, ctx), els };
}

test('who can go out: same position, affordable (bank + his selling price), club limit', () => {
  const { run } = setup();
  const o = JSON.parse(run('JSON.stringify(tryOptions(16, 11))'));
  assert.equal(o.all.length, 5);                    // the five MIDs
  assert.deepEqual(o.ok.map(x => x.id), [12]);      // only P12 sells for £5.4m: £0.7m + £5.4m covers £6m
  assert.match(o.all.find(x => x.id === 8).why, /short by £0\.3m/);
  // the club limit: two more from club 9 in the squad, then a third MID from club 9 can't come in
  run('P[3].team = 9; P[8].team = 9');               // club 9: P3, P8 and P9
  const c = JSON.parse(run('JSON.stringify(tryOptions(17, 11))'));
  assert.ok(c.ok.some(x => x.id === 8));                         // swapping out a club-9 player keeps it at 3
  assert.match(c.all.find(x => x.id === 10).why, /3 from C9 already/);
});

test('the preview never changes the plan; Apply matches it and Undo takes it back', () => {
  const { run } = setup();
  run('SB.moves = [{ gw: 12, out: 13, in: 15 }]; SB.moves = cleanMoves(SB.moves)');   // a no-op move, just to have one
  const before = run('JSON.stringify([SB.moves, SB.prev])');
  const r = JSON.parse(run('JSON.stringify(tryPreview(16, 11, 12))'));
  assert.equal(run('JSON.stringify([SB.moves, SB.prev])'), before);       // untouched
  assert.equal(r.added, true);
  assert.equal(r.sell, 5.4); assert.equal(r.buy, 6);
  assert.equal(r.bankBefore, 0.7); assert.equal(Math.round(r.bankAfter * 10) / 10, 0.1);
  assert.equal(r.extraHits, 0);
  assert.equal(Math.round(r.playerDiff * 10) / 10, 3 * (6 - 1));          // P12 is a 1-xP bench MID: +15 over GW11-13
  run('openTry(16)');
  run('document.querySelector("#tryApply").onclick()');
  assert.equal(run('SB.moves.some(m => m.gw === 11 && m.out === 12 && m.in === 16)'), true);
  assert.equal(run('SB.source'), 'custom');
  const shown = run('scoreMoves(SB.moves).tot + ftValue() * scoreMoves(SB.moves).ftLeft');
  assert.ok(Math.abs(shown - r.planAfter) < 1e-9, `${shown} v ${r.planAfter}`);   // what the Planner shows = the preview
  run('undoPlan()');
  assert.equal(run('JSON.stringify(SB.moves)'), JSON.stringify(JSON.parse(before)[0]));
});

test('a second move in a week with one free transfer costs a hit; a later move it breaks is listed', () => {
  const { run } = setup();
  run('D.manager.bank = 5; SB.moves = cleanMoves([{ gw: 11, out: 3, in: 18 }, { gw: 12, out: 12, in: 17 }])');
  assert.equal(run('SB.moves.length'), 2);
  // GW12 plans to sell P12; selling P12 in GW11 for Star makes that impossible
  const r = JSON.parse(run('JSON.stringify(tryPreview(16, 11, 12))'));
  assert.equal(r.extraHits, 1);                                  // 1 FT in GW11, already used
  assert.equal(r.dropped.length, 1);
  assert.equal(r.dropped[0].gw, 12);
  run('openTry(16); TRY.out = 12; openTry(16)');      // you choose P12, whom GW12 also sells
  const html = run('document.querySelector("#dlgBody").innerHTML');
  assert.match(html, /−4 pts/);
  assert.match(html, /GW11: a −4 hit \(no free transfer left\)/);
  assert.match(html, /impossible, so it is dropped on Apply: GW12 P12 → Other/);
});

test('a Free Hit week: the move is free and lasts that week only', () => {
  const { run } = setup();
  run('SB.chips = cleanChips({ freehit: 12 })');
  const r = JSON.parse(run('JSON.stringify(tryPreview(16, 12, 12))'));
  assert.equal(r.chip, 'freehit');
  assert.equal(r.extraHits, 0);
  assert.equal(run(`JSON.stringify(squadAt(13, ${JSON.stringify(r.cand)}, SB.chips).includes(16))`), 'false');
  run('TRY.id = null; openTry(16); document.querySelector("#tryGw").onchange({ target: { value: "12" } })');
  assert.match(run('document.querySelector("#dlgBody").innerHTML'), /Free Hit week: this move lasts that week only/);
});

test('already in the squad, or nobody can go out: said, and Apply is off', () => {
  const { run } = setup();
  run('openTry(8)');
  assert.match(run('document.querySelector("#dlgBody").innerHTML'), /already in your plan's GW11 squad[\s\S]*id="tryApply" disabled/);
  run('D.manager.bank = 0; TRY.id = null; openTry(16)');
  assert.match(run('document.querySelector("#dlgBody").innerHTML'), /No MID in your GW11 squad can go out for him: P8 \(short by £1\.0m\)/);
});

test('the default player out keeps later planned moves possible', () => {
  const { run } = setup();
  // P12 (1 xP) is the lowest, but the plan sells him in GW12; with money for anyone, P8 is picked instead
  run('D.manager.bank = 5; SB.moves = cleanMoves([{ gw: 12, out: 12, in: 17 }]); openTry(16)');
  assert.equal(run('TRY.out'), 8);
  run('SB.moves = []; TRY.id = null; openTry(16)');
  assert.equal(run('TRY.out'), 12);                   // nothing planned: the lowest xP
});
