// Property tests: rules a squad, a transfer plan and the chips must never break, on many random leagues and plans.
// The Python half (optimise.py) is tests/test_plan_properties.py.
//
// CLAUDE.md doesn't say new dependencies may be added, so this uses a small seeded generator (mulberry32) instead of
// fast-check. Every case is reproducible from its seed (printed on failure) and the run is identical every time.
//
// Part 1, the browser solver (site/plan-solver.js, the shipped HiGHS build) with random chip pins, checked by rules
// written here, not by the solver's own read-back:
//   15 players in the right shape and at most 3 a club every week (the Free Hit squad too); a valid XI and captain;
//   bank never below £0 across the plan; a Free Hit squad within bank plus the held squad's value, and the old squad
//   back the week after; Wildcard and Free Hit weeks take no hit and keep banked transfers (+1, up to 5); hits are the
//   moves beyond free transfers otherwise; maxHits and the weekly move cap respected; value adds up (Bench Boost
//   counts the bench, Triple Captain the armband once more).
// Part 2, the Planner's own bookkeeping (site/js/core/plan.js), against a plain re-implementation of FPL's rules:
//   cleanChips keeps one chip a gameweek, only in the plan's weeks and the chip's window; cleanMoves + squadAt keep 15
//   distinct players in the right shape and drop Free Hit moves after that week; bankAt matches the money the moves
//   leave; ftTable's free transfers stay 1-5 with the right hits and chip rules.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import makeHighs from "../site/vendor/highs.js";
import solver from "../site/plan-solver.js";

const RULES = JSON.parse(readFileSync(new URL("./fixtures/plan_rules.json", import.meta.url), "utf8"));
const SETTINGS = solver.settingsFrom(RULES);
const SHAPE = { GKP: 2, DEF: 5, MID: 5, FWD: 3 }, XI_MIN = { GKP: 1, DEF: 3, MID: 2, FWD: 1 }, XI_MAX = { GKP: 1, DEF: 5, MID: 5, FWD: 3 };
const PRICE = { GKP: [4.0, 6.0], DEF: [4.0, 7.5], MID: [4.5, 12.5], FWD: [4.5, 14.0] };

function rng(seed) {   // mulberry32: small, fast, good enough for test inputs
  let a = seed >>> 0;
  const next = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const r = { next, uni: (lo, hi) => lo + (hi - lo) * next(), int: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)),
    pick: xs => xs[Math.floor(next() * xs.length)],
    shuffle: xs => { for (let i = xs.length - 1; i > 0; i--) { const j = Math.floor(next() * (i + 1)); [xs[i], xs[j]] = [xs[j], xs[i]]; } return xs; } };
  return r;
}
const r1 = x => Math.round(x * 10) / 10;

// a random league (20 clubs) and a legal squad of 15 from it
function league(R, gws, n = { GKP: 8, DEF: 20, MID: 20, FWD: 12 }) {
  const players = {};
  let id = 0;
  for (const [pos, k] of Object.entries(n)) for (let j = 0; j < k; j++) {
    const [lo, hi] = PRICE[pos], price = r1(R.uni(lo, hi)), base = R.uni(0.5, 2) + (price - lo) * R.uni(0.2, 0.6);
    players[++id] = { id, pos, team: R.int(1, 20), price, ok: R.next() > 0.08, nailed: 100,
      xp: Object.fromEntries(gws.map(g => [g, Math.round(Math.max(0, base + R.uni(-1.5, 1.5)) * 100) / 100])) };
  }
  return players;
}
function squadOf(R, players) {
  for (let t = 0; t < 1000; t++) {
    const sq = [], clubs = {};
    let ok = true;
    for (const [pos, k] of Object.entries(SHAPE)) {
      let need = k;
      for (const p of R.shuffle(Object.values(players).filter(p => p.pos === pos))) {
        if (!need) break;
        if ((clubs[p.team] || 0) < 3) { sq.push(p.id); clubs[p.team] = (clubs[p.team] || 0) + 1; need--; }
      }
      ok = ok && need === 0;
    }
    if (ok) return sq;
  }
  throw new Error("couldn't draw a legal squad");
}
const sellOf = (R, players, squad) => Object.fromEntries(squad.map(i => [i, r1(Math.max(3.5, players[i].price - R.pick([0, 0, 0.1, 0.2, 0.3])))]));

function shapeProblems(P, ids, tag) {
  const out = [], clubs = {};
  if (ids.length !== 15 || new Set(ids).size !== 15) out.push(`${tag}: ${new Set(ids).size} different players, not 15`);
  for (const [pos, k] of Object.entries(SHAPE)) { const c = ids.filter(i => P[i].pos === pos).length; if (c !== k) out.push(`${tag}: ${c} ${pos}, not ${k}`); }
  ids.forEach(i => { clubs[P[i].team] = (clubs[P[i].team] || 0) + 1; });
  Object.entries(clubs).forEach(([t, c]) => c > 3 && out.push(`${tag}: ${c} from club ${t}`));
  return out;
}

// every rule the browser solver's plan breaks ([] if none)
function solverProblems(inp, r) {
  const P = inp.players, out = [], sp = i => inp.sell[i] ?? P[i].price;
  let have = inp.squad.slice(), money = inp.bank, ft = inp.ft0, value = 0;
  const owned = new Set(inp.squad);
  inp.gws.forEach((g, w) => {
    const wk = r.weeks[w], chip = Object.keys(inp.chips || {}).find(k => inp.chips[k] === g) || null;
    const tag = `GW${g}${chip ? ` (${chip})` : ""}`;
    if ((wk.chip || null) !== chip) out.push(`${tag}: plan says chip ${wk.chip}`);
    const mv = r.moves.filter(m => m.gw === g), n = mv.length;
    const before = have.slice(), worth = money + before.reduce((a, i) => a + (owned.has(i) ? sp(i) : P[i].price), 0);
    for (const m of mv) {
      if (!have.includes(m.out)) out.push(`${tag}: sells ${m.out}, not owned`);
      if (have.includes(m.in)) out.push(`${tag}: buys ${m.in}, already owned`);
      if (!P[m.in].ok) out.push(`${tag}: buys unavailable ${m.in}`);
      if (P[m.in].pos !== P[m.out].pos) out.push(`${tag}: ${P[m.out].pos} out, ${P[m.in].pos} in`);
      money += owned.has(m.out) ? sp(m.out) : P[m.out].price; owned.delete(m.out);
      money -= P[m.in].price;
      have = have.map(i => i === m.out ? m.in : i);
    }
    if (money < -0.05) out.push(`${tag}: bank below £0 (£${money.toFixed(1)}m)`);
    out.push(...shapeProblems(P, have, tag));
    const played = chip === "freehit" ? wk.squad : have;
    if (chip === "freehit") {
      if (n) out.push(`${tag}: ${n} real transfers in a Free Hit week`);
      out.push(...shapeProblems(P, played, tag + " squad"));
      const cost = played.reduce((a, i) => a + P[i].price, 0);
      if (cost > worth + 0.05) out.push(`${tag}: Free Hit squad costs £${cost.toFixed(1)}m, only £${worth.toFixed(1)}m to spend`);
    } else if ([...played].sort((a, b) => a - b).join() !== [...wk.squad].sort((a, b) => a - b).join()) {
      out.push(`${tag}: plan's squad isn't the one its moves give`);
    }
    const xi = wk.xi;
    if (xi.length !== 11 || new Set(xi).size !== 11 || xi.some(i => !played.includes(i))) out.push(`${tag}: XI isn't 11 from the squad`);
    for (const pos in SHAPE) { const c = xi.filter(i => P[i].pos === pos).length; if (c < XI_MIN[pos] || c > XI_MAX[pos]) out.push(`${tag}: ${c} ${pos} in the XI`); }
    if (!xi.includes(wk.captain)) out.push(`${tag}: captain not in the XI`);
    if (chip !== "wildcard" && n > inp.maxMovesWeek) out.push(`${tag}: ${n} moves, over the weekly cap`);
    if (w === 0 && inp.week1Moves != null && n !== inp.week1Moves) out.push(`${tag}: ${n} moves, asked for ${inp.week1Moves}`);
    if (wk.ft !== ft) out.push(`${tag}: plan says ${wk.ft} FT, FPL's rules give ${ft}`);
    const free = chip === "wildcard" || chip === "freehit", hits = free ? 0 : Math.max(0, n - ft);
    if (wk.hits !== hits) out.push(`${tag}: ${wk.hits} hits, FPL's rules give ${hits}`);
    if (inp.maxHits != null && wk.hits > inp.maxHits) out.push(`${tag}: ${wk.hits} hits, allowed ${inp.maxHits}`);
    ft = free ? Math.min(5, ft + 1) : n > ft ? 1 : Math.min(5, ft - n + 1);
    const x = i => P[i].xp[g] || 0;
    value += (chip === "bboost" ? played : xi).reduce((a, i) => a + x(i), 0) + x(wk.captain) * (chip === "3xc" ? 2 : 1) - inp.hit * wk.hits;
  });
  if (r.ftLeft !== ft) out.push(`ftLeft ${r.ftLeft}, FPL's rules give ${ft}`);
  value += inp.ftValue * ft;
  if (Math.abs(value - r.value) > 0.02) out.push(`value ${r.value.toFixed(2)}, its weeks add up to ${value.toFixed(2)}`);
  return out;
}

const CHIPS = ["wildcard", "freehit", "bboost", "3xc"];
function solverCase(seed) {
  const R = rng(seed), gws = [11, 12, 13], players = league(R, gws), squad = squadOf(R, players);
  // make breaking a rule pay, or random leagues almost never test it: a weak squad (so hits look worth taking) and a
  // club of cheap, far better players you don't own (so a plan ignoring the 3-a-club limit would load up on them)
  if (R.next() < 0.5) squad.forEach(i => { players[i].xp = Object.fromEntries(gws.map(g => [g, 0.5])); });
  if (R.next() < 0.5) {
    const club = 7;
    Object.values(players).filter(p => !squad.includes(p.id)).forEach((p, k) => {
      if (p.team === club || k % 9 === 0) { p.team = club; p.price = PRICE[p.pos][0]; p.ok = true; p.xp = Object.fromEntries(gws.map(g => [g, p.xp[g] + 6])); }
    });
  }
  const chips = {};
  R.shuffle(CHIPS.slice()).slice(0, R.int(0, 2)).forEach(c => {
    const g = R.pick(gws);
    if (!Object.values(chips).includes(g)) chips[c] = g;
  });
  const ft0 = R.int(1, 5), maxHits = R.pick([0, 1, null]);
  let week1Moves = R.pick([null, null, 0, 1, 2]);
  if (chips.freehit === gws[0] && week1Moves) week1Moves = 0;   // a Free Hit week makes no real transfers
  if (week1Moves && maxHits != null && chips.wildcard !== gws[0] && week1Moves > ft0 + maxHits) week1Moves = ft0;
  return { ...SETTINGS, players, squad, sell: sellOf(R, players, squad), bank: r1(R.uni(0, 3)), ft0, gws, locked: [], banned: [],
    maxHits, week1Moves, chips };
}

test("browser solver: random leagues, squads and chip pins keep every rule", async () => {
  const highs = await makeHighs();
  const bad = [];
  for (let seed = 1; seed <= 16; seed++) {
    const inp = solverCase(seed);
    let r;
    try { r = await solver.solve(highs, inp, makeHighs); } catch (e) { bad.push(`seed ${seed} (chips ${JSON.stringify(inp.chips)}): ${e.message}`); continue; }
    const p = solverProblems(inp, r);
    if (p.length) bad.push(`seed ${seed} (chips ${JSON.stringify(inp.chips)}, ft0 ${inp.ft0}, maxHits ${inp.maxHits}, week1 ${inp.week1Moves}): ${p.join("; ")}`);
  }
  assert.deepEqual(bad, []);
});

// ---------------------------------------------------------------- Part 2: plan.js bookkeeping
function planApp() {
  const ctx = vm.createContext({ location: { hash: "" }, setTimeout, localStorage: { getItem: () => null, setItem: () => {} },
    document: { querySelectorAll: () => [], querySelector: () => null } });
  for (const file of ["core/state", "core/model", "core/plan"]) vm.runInContext(readFileSync(new URL("../site/js/" + file + ".js", import.meta.url), "utf8"), ctx);
  return ctx;
}

test("plan.js: chips, moves, squads, bank and free transfers on random plans follow FPL's rules", () => {
  const ctx = planApp(), bad = [];
  for (let seed = 1; seed <= 300; seed++) {
    const R = rng(1000 + seed), PG = [11, 12, 13, 14, 15], players = league(R, PG), squad = squadOf(R, players);
    const sell = sellOf(R, players, squad), bank = r1(R.uni(0, 3)), ft0 = R.int(1, 5);
    // chips on offer: each available or not, in a window that may or may not cover the plan
    const chipsOffer = CHIPS.map(key => ({ key, available: R.next() > 0.2, from: R.pick([1, 11, 13]), to: R.pick([12, 19, 38]) }));
    const pins = {};
    CHIPS.forEach(c => { if (R.next() < 0.5) pins[c] = R.pick([...PG, 9, 16]); });   // some outside the plan
    ctx.D = { squad: squad.map(id => ({ id, sell: sell[id], buy: sell[id] })), manager: { bank, free_transfers: ft0 }, chips: chipsOffer, meta: { team_id: 1, next_gw: 11 } };
    ctx.P = players; ctx.PG = PG; ctx.SB = null;
    vm.runInContext("D = globalThis.D; P = globalThis.P; PG = globalThis.PG; SB = globalThis.SB;", ctx);
    const chips = ctx.cleanChips(pins);
    const tag = `seed ${1000 + seed}`;
    // cleanChips: one chip a week, in the plan, in an available window
    const weeks = Object.values(chips);
    if (new Set(weeks).size !== weeks.length) bad.push(`${tag}: two chips in one week ${JSON.stringify(chips)}`);
    for (const [k, g] of Object.entries(chips)) {
      const c = chipsOffer.find(x => x.key === k);
      if (!PG.includes(g) || !c.available || g < c.from || g > c.to) bad.push(`${tag}: kept ${k} in GW${g} (${JSON.stringify(c)})`);
      if (pins[k] !== g) bad.push(`${tag}: moved ${k} from GW${pins[k]} to GW${g}`);
    }
    for (const [k, g] of Object.entries(pins)) {
      const c = chipsOffer.find(x => x.key === k);
      const allowed = PG.includes(g) && c.available && g >= c.from && g <= c.to;
      if (allowed && !(k in chips) && !Object.entries(chips).some(([k2, g2]) => g2 === g && k2 !== k)) bad.push(`${tag}: dropped legal ${k} in GW${g}`);
    }
    // random same-position moves, some of them stale (selling someone no longer owned)
    const moves = [];
    let cur = squad.slice();
    for (const g of PG) for (let k = R.int(0, 2); k > 0; k--) {
      const out = R.next() < 0.9 ? R.pick(cur) : R.pick(Object.keys(players).map(Number));
      const cands = Object.values(players).filter(p => p.pos === players[out].pos && !cur.includes(p.id));
      if (!cands.length) continue;
      const inn = R.pick(cands).id;
      moves.push({ gw: g, out, in: inn });
      if (cur.includes(out) && chips.freehit !== g) cur = cur.map(i => i === out ? inn : i);
    }
    const clean = ctx.cleanMoves(moves, chips);
    // oracle: apply moves in order, a Free Hit week's to a copy that is thrown away after that week
    let real = squad.slice(), money = bank;
    const owned = new Set(squad), sp = i => owned.has(i) ? sell[i] : players[i].price;
    let ft = Math.min(5, ft0);
    for (const g of PG) {
      const fh = chips.freehit === g;
      let sq = real.slice(), m2 = money;
      const kept = clean.filter(m => m.gw === g);
      for (const m of kept) {
        if (!sq.includes(m.out) || sq.includes(m.in)) bad.push(`${tag} GW${g}: cleanMoves kept a move that can't be made`);
        m2 += sp(m.out); m2 -= players[m.in].price;
        sq = sq.map(i => i === m.out ? m.in : i);
      }
      const got = ctx.squadAt(g, clean, chips);
      if ([...got].sort().join() !== [...sq].sort().join()) bad.push(`${tag} GW${g}: squadAt differs from the moves`);
      shapeProblems(players, got, `${tag} GW${g}`).filter(p => !/from club/.test(p)).forEach(p => bad.push(p));
      const b = ctx.bankAt(g, clean, chips);
      if (Math.abs(b - r1(m2)) > 0.051) bad.push(`${tag} GW${g}: bankAt £${b}m, moves leave £${m2.toFixed(1)}m`);
      if (!fh) {
        for (const m of kept) owned.delete(m.out);
        real = sq; money = m2;
      }
      const row = ctx.ftTable(clean, PG, chips).find(x => x.gw === g);
      const n = kept.length, chip = Object.keys(chips).find(k => chips[k] === g) || null;
      const free = chip === "wildcard" || chip === "freehit", hits = free ? 0 : Math.max(0, n - ft);
      if (row.ft !== ft || row.hits !== hits || row.n !== n || row.chip !== chip) bad.push(`${tag} GW${g}: ftTable ${JSON.stringify(row)}, FPL: ft ${ft}, ${n} moves, ${hits} hits, chip ${chip}`);
      ft = free ? Math.min(5, ft + 1) : n > ft ? 1 : Math.min(5, ft - n + 1);
      if (row.next !== ft || ft < 1 || ft > 5) bad.push(`${tag} GW${g}: next FT ${row.next}, FPL: ${ft}`);
    }
  }
  assert.deepEqual(bad.slice(0, 20), []);
});
