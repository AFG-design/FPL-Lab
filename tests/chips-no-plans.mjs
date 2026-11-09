import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../site/js/views/chips.js', import.meta.url), 'utf8');
function render(gwInfo, { doubles=false, used=false }={}) {
  const D={meta:{next_gw:11},plans:gwInfo?.length?{roll:{weeks:gwInfo}}:{},gw_info:gwInfo,
    chips:[{key:'3xc',name:'Triple Captain',from:1,to:19,available:!used,used:used?9:null},
      {key:'wildcard',name:'Wildcard',from:1,to:19,used:8},
      {key:'bboost',name:'Bench Boost',from:1,to:19,available:true}],
    season_gws:[{gw:12,doubles:doubles?['ARS']:[],blanks:[]}]};
  const ctx=vm.createContext({D,P:{1:{name:'Salah'},2:{name:'Haaland'}},esc:String,f1:n=>n.toFixed(1)});
  vm.runInContext(source,ctx);
  return vm.runInContext('vChips()',ctx);
}
for(const [name,info,options] of [
  ['empty projections',[],{}],['missing projections',undefined,{}],['null projections',null,{}],
  ['double scheduled',[],{doubles:true}],['TC already used',[],{used:true}],
]) test(`Chips without plans: ${name}`,()=>{
  const html=render(info,options);
  assert.match(html,/No projection for the best week yet/);
  assert.match(html,/Used GW8/);
  assert.match(html,/Bench Boost/);
  assert.match(html,/Available/);
  assert.match(html,/GW1–19/);
  assert.doesNotMatch(html,/undefined|NaN|In view now/);
  if(options.doubles) assert.match(html,/GW12 double: ARS/);
});
const weeks=[{gw:11,squad_playing:15,bench_xp:8,tc_player:1,tc_xp:5},
  {gw:12,squad_playing:14,bench_xp:7,tc_player:2,tc_xp:7}];
test('Chips with projections retains best-week advice and table',()=>{
  const html=render(weeks);
  assert.match(html,/In view now: <b>GW12<\/b> \(Haaland, 21.0 pts with TC\)/);
  assert.match(html,/next 2 gameweeks/);
  assert.match(html,/15\/15/);
  assert.match(html,/14\/15/);
  assert.match(html,/>15.0<\/td>/);
  assert.match(html,/>21.0<\/td>/);
  assert.doesNotMatch(html,/No projection/);
});
test('Chips with a double keeps the existing double-week advice',()=>{
  const html=render(weeks,{doubles:true});
  assert.match(html,/A double gameweek falls before then, which is the best spot/);
  assert.doesNotMatch(html,/In view now|No projection/);
});
