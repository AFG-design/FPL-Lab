import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

// FL-088: the plan only ever syncs to a repository GitHub reports as private, never to the public site repository.
function setup({ token = 'tok', repo = 'me/fpl-lab-sync', reply } = {}) {
  const ls = new Map(); if (token) ls.set('fpl.gh', token); if (repo) ls.set('fpl.syncRepo', repo);
  const calls = [];
  const ctx = vm.createContext({
    location: { hash: '' }, document: { querySelector: () => ({ addEventListener() {} }) },
    localStorage: { getItem: k => ls.get(k) ?? null, setItem: (k, v) => ls.set(k, String(v)), removeItem: k => ls.delete(k) },
    setInterval: () => 0, setTimeout: () => 0, clearTimeout() {}, btoa, atob, escape, unescape, encodeURIComponent, decodeURIComponent,
    fetch: async (url, opt = {}) => { calls.push({ url: String(url), opt }); if (url.includes('/actions/')) return { ok: false, status: 404 }; return reply ? reply(String(url), opt) : { ok: false, status: 404 }; },
  });
  for (const f of ['core/state', 'data/github']) vm.runInContext(readFileSync(new URL(`../site/js/${f}.js`, import.meta.url), 'utf8'), ctx);
  return { run: e => vm.runInContext(e, ctx), calls, ls };
}
const repoReply = (status, body) => async () => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test('sync is off without a private repository, even with a token saved', () => {
  const { run } = setup({ repo: '' });
  assert.equal(run('syncReady()'), false);
  assert.equal(run('syncRepo()'), '');
});
test('the public site repository and malformed names are never used', () => {
  for (const repo of ['AFG-design/FPL-Lab', 'afg-design/fpl-lab', 'no-slash', 'a/b/c', 'me/re po', '../x']) {
    const { run } = setup({ repo });
    assert.equal(run('syncRepo()'), '', repo);
    assert.equal(run('syncReady()'), false, repo);
  }
});
test('reading without setup fails instead of falling back to the old public branch', async () => {
  const { run, calls } = setup({ repo: '' });
  await assert.rejects(run('syncGet()'), /isn't set up/);
  assert.equal(calls.filter(c => c.url.includes('/contents/')).length, 0);
});
test('reads and writes go to the private repository, on its default branch, with the token', async () => {
  const { run, calls } = setup({ reply: async url => url.includes('/contents/') ? { ok: false, status: 404 } : { ok: true, status: 200, json: async () => ({}) } });
  const got = await run('syncGet()');
  assert.deepEqual(JSON.parse(JSON.stringify(got)), { doc: { plans: {} }, sha: null });   // no plan.json yet: starts empty
  const c = calls.find(x => x.url.includes('/contents/'));
  assert.match(c.url, /^https:\/\/api\.github\.com\/repos\/me\/fpl-lab-sync\/contents\/plan\.json\?t=/);
  assert.doesNotMatch(c.url, /ref=|FPL-Lab/);
  assert.equal(c.opt.headers.Authorization, 'Bearer tok');
});
test('nothing in the sync code names the old branch or writes to the site repository', () => {
  const src = readFileSync(new URL('../site/js/data/github.js', import.meta.url), 'utf8');
  assert.doesNotMatch(src, /SYNC\.branch|ref=\$\{SYNC|branch: /);
  const put = src.split('\n').filter(l => l.includes('method: "PUT"'));
  assert.equal(put.length, 1);
  assert.match(put[0], /repos\/\$\{syncRepo\(\)\}\/contents/);
});
test('a repository is accepted only when GitHub says it is private', async () => {
  const check = async (reply, repo = 'me/fpl-lab-sync', token = 'tok') => JSON.parse(JSON.stringify(await setup({ reply }).run(`syncRepoCheck(${JSON.stringify(repo)}, ${JSON.stringify(token)})`)));
  assert.deepEqual(await check(repoReply(200, { private: true })), { ok: true });
  assert.match((await check(repoReply(200, { private: false }))).why, /public/);
  assert.match((await check(repoReply(200, {}))).why, /public/);                       // no answer is not a yes
  assert.match((await check(repoReply(404, {}))).why, /can't see that repository/);
  assert.match((await check(repoReply(401, {}))).why, /refused the token/);
  assert.match((await check(repoReply(500, {}))).why, /GitHub said 500/);
  assert.match((await check(async () => { throw new Error('offline'); })).why, /Couldn't reach GitHub/);
  assert.match((await check(repoReply(200, { private: true }), 'AFG-design/FPL-Lab')).why, /public site repository/);
  assert.match((await check(repoReply(200, { private: true }), 'nonsense')).why, /owner\/name/);
  assert.match((await check(repoReply(200, { private: true }), 'me/fpl-lab-sync', '')).why, /token first/);
});
test('the refresh button still targets the site repository', () => {
  const src = readFileSync(new URL('../site/js/data/github.js', import.meta.url), 'utf8');
  assert.match(src, /repos\/\$\{REPO\}\/actions\/workflows\/refresh\.yml\/dispatches/);
});
