import assert from 'node:assert/strict';
import test from 'node:test';
import { fixture } from './support/decision-fixture.mjs';
test('only plan-specific affordability changes appear, baseline stable on refresh', () => {
  const run = fixture();
  run("const draft = {id:'a',name:'A',...completePlan({moves:[{gw:11,out:8,in:16}]})}; draft.review = planReviewSnapshot(draft); setDrafts([draft]); P[16].price = 5.1");
  assert.match(run('planReviewHTML(getDrafts()[0])'),/unaffordable.*£0.0m → £-0.1m/);
  const before = run('JSON.stringify(PLAN_REVIEWS.get(planReviewKey(draft)))');
  run('D.meta.built = new Date().toISOString()');
  assert.match(run('planReviewHTML(getDrafts()[0])'),/unaffordable/);
  assert.equal(run('JSON.stringify(PLAN_REVIEWS.get(planReviewKey(draft)))'),before);
});
test('unrelated price change produces no material change', () => {
  const run = fixture();
  run("const d = {id:'a',name:'A',...completePlan()}; d.review=planReviewSnapshot(d); setDrafts([d]); P[16].price=8");
  assert.match(run('planReviewHTML(getDrafts()[0])'),/No material changes/);
});
test('reviewing an old draft establishes only its own baseline', () => {
  const run = fixture();
  run("setDrafts([{id:'a',name:'A',...completePlan()},{id:'b',name:'B',...completePlan()}])");
  assert.match(run('planReviewHTML(getDrafts()[0])'),/First review/);
  assert.equal(run('!!getDrafts()[0].review'),true);
  assert.equal(run('getDrafts()[1].review'),undefined);
});
test('starter flags, fixtures and captain recommendations compare actual facts', () => {
  const run = fixture();
  run("const d = completePlan(); const before = planReviewSnapshot(d); P[15].status='i'; P[15].chance=0; T[15].fx[11]=[]; P[14].xp[11]=100");
  const text = run('planReviewDiff(before, planReviewSnapshot(d)).join(" ")');
  assert.match(text,/Player 15: available.*injured/);
  assert.match(text,/Player 15, GW11:.*Blank/);
  assert.match(text,/recommended captain Player 15 → Player 14/);
});
