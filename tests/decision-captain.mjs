import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
function fixture(extra = []) {
  const mem = {};
  const ctx = vm.createContext({ location: { hash: '' }, localStorage: { getItem: k => mem[k] || null, setItem: (k,v) => mem[k] = v } });
  for (const f of ['core/state', 'core/model', 'core/plan', 'views/planner', 'views/planner-views', 'views/tpaths', ...extra]) {
    vm.runInContext(readFileSync(`site/js/${f}.js`, 'utf8'), ctx);
  }
  vm.runInContext(`
    const pos = ['GKP','GKP',...Array(5).fill('DEF'),...Array(5).fill('MID'),...Array(3).fill('FWD'),'MID'];
    const players = pos.map((pos,k) => ({id:k+1, name:'Player '+(k+1), pos, team:k+1, price:5, status:'a', chance:100, xp:{11:k+1,12:2*(k+1)}, ok:true}));
    P = Object.fromEntries(players.map(p => [p.id,p]));
    T = Object.fromEntries(players.map(p => [p.team,{short:'Club '+p.team,fx:{11:[{opp:20,home:true}],12:[{opp:20,home:true},{opp:19,home:false}]}}]));
    D = {meta:{next_gw:11,team_id:1,built:new Date().toISOString()},players,squad:players.slice(0,15).map(p=>({id:p.id,sell:5})),
      chips:[{key:'bboost',from:1,to:19,available:true}], manager:{bank:0,free_transfers:5},plan_rules:{ft_value:1.5}};
    GWS = PG = [11,12]; SB = {moves:[],ov:{},chips:{},solved:null,source:'custom',rules:{locked:[],banned:[]}};
    syncPush = () => {};
  `,ctx);
  return s => vm.runInContext(s,ctx);
}

for (const tc of [false,true]) test(`captain comparison fixes all XIs and moves, including TC=${tc}`, () => {
  const run = fixture(['views/decisions']);
  run(`SB.chips=${tc ? '{"3xc":11}' : '{}'}; drawDecision=()=>{};
    const a=completePlan(), sc=decisionScore(a), w=sc.weeks[0];
    DECISION={original:a,xi:w.team.xi,cap:w.team.cap};
    const original=JSON.stringify(SB); setDecisionCaptain(w.team.vice);`);
  assert.equal(run('JSON.stringify(SB)'),run('original'));
  assert.equal(run('JSON.stringify(decisionScore(DECISION.a).weeks.map(w=>w.team.xi))'),run('JSON.stringify(decisionScore(DECISION.b).weeks.map(w=>w.team.xi))'));
  assert.equal(run('JSON.stringify(DECISION.a.moves)'),run('JSON.stringify(DECISION.b.moves)'));
  assert.ok(run('Math.abs(decisionScore(DECISION.a).tot-decisionScore(DECISION.b).tot-(xpg(DECISION.cap,11)-xpg(DECISION.selected,11))*(SB.chips["3xc"]===11?2:1))<1e-8'));
});
