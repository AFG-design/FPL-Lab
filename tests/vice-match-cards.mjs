import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function setup({capMinutes=0, started=true, done=true, chip=null, double=false, viceMinutes=90}={}) {
  const D = {meta:{deadline:'2099-01-01'},live:{gw:11,chip,
    rows:[{id:1,team:1,pos:1,cap:true,mins:capMinutes,pts:capMinutes?5:0,prov:0},
          {id:2,team:2,pos:2,vice:true,mins:viceMinutes,pts:viceMinutes?5:0,prov:viceMinutes?1:0}],
    fixtures:[{h:1,a:3,started,done,ko:'2026-11-08T15:00:00Z'},
              {h:2,a:3,started:true,done:true,ko:'2026-11-08T17:00:00Z'}]}};
  if(double) D.live.fixtures.push({h:1,a:3,started:false,done:false,ko:'2026-11-10T15:00:00Z'});
  const ctx=vm.createContext({D,P:{1:{name:'Captain',pos:'GKP'},2:{name:'Vice',pos:'DEF'}},
    T:{1:{name:'One'},2:{name:'Two'},3:{name:'Three'}},esc:String,badge:()=>''});
  for(const name of ['live','scores']) vm.runInContext(readFileSync(new URL(`../site/js/views/${name}.js`,import.meta.url),'utf8'),ctx);
  const run=expr=>vm.runInContext(expr,ctx);
  return {D,run,html:()=>run('scoresStrip()')};
}
function points(html,id) {
  return [...html.matchAll(new RegExp(`data-p="${id}" class="mc-p">([^<]*)<b>([^<]*)</b>`, 'g'))].map(m=>({name:m[1],points:m[2]}));
}
for(const [name,options,capPoints,vicePoints,viceCaptain] of [
  ['captain plays',{capMinutes:90},'10','6',false],
  ['captain confirmed out',{},'0','12',true],
  ['captain still to come',{started:false,done:false},'–','6',false],
  ['Triple Captain passes to vice',{chip:'3xc'},'0','18',true],
  ['captain match in progress',{started:true,done:false},'0','6',false],
  ['double: second captain fixture pending',{double:true},'0','6',false],
  ['vice has not played either',{viceMinutes:0},'0','0',false],
]) test(name,()=>{
  const f=setup(options),html=f.html(),state=f.run('liveState()');
  assert.equal(points(html,1)[0].points,capPoints);
  assert.equal(points(html,2)[0].points,vicePoints);
  assert.equal(points(html,2)[0].name,viceCaptain?'Vice (C)':'Vice');
  if(capPoints!=='–') assert.equal(Number(capPoints),state.rows[0].live*state.mult(state.rows[0]));
  assert.equal(Number(vicePoints),state.rows[1].live*state.mult(state.rows[1]));
  if(viceCaptain) assert.equal(points(html,1)[0].name,'Captain');
});

test('missing squad data keeps match scores with a clear unavailable message',()=>{
  const f=setup(); delete f.D.live.rows;
  assert.match(f.html(),/Player points unavailable/);
  assert.match(f.html(),/class="mcard/);
  assert.doesNotMatch(f.html(),/class="mc-p"/);
});
