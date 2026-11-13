// FL-147: the FPL School relay passes on a team and its picks only, GET only, to the site's address, and stores nothing.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { allowed, handle } from '../workers/fpl-school-relay.mjs';

const req = (path, { method = 'GET', origin = 'https://afg-design.github.io' } = {}) =>
  new Request('https://relay.example' + path, { method, headers: { Origin: origin } });
const fpl = [];
const fakeFetch = async (url) => { fpl.push(url); return new Response('{"name":"X"}', { status: 200 }); };

test('only a team and its picks are allowed', () => {
  assert.ok(allowed('/entry/8122679/'));
  assert.ok(allowed('/entry/8122679/event/10/picks/'));
  for (const p of ['/bootstrap-static/', '/entry/abc/', '/entry/1/history/', '/entry/1/transfers/', '/my-team/1/', '/entry/1/event/10/picks/../../'])
    assert.ok(!allowed(p), p);
});

test('passes the team on from FPL with the site as the allowed origin', async () => {
  const r = await handle(req('/entry/123/'), fakeFetch);
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), 'https://afg-design.github.io');
  assert.equal(fpl.at(-1), 'https://fantasy.premierleague.com/api/entry/123/');
  assert.deepEqual(await r.json(), { name: 'X' });
});

test('refuses everything else without asking FPL', async () => {
  const n = fpl.length;
  assert.equal((await handle(req('/bootstrap-static/'), fakeFetch)).status, 404);
  assert.equal((await handle(req('/entry/123/', { method: 'POST' }), fakeFetch)).status, 405);
  assert.equal(fpl.length, n);
  const other = await handle(req('/entry/123/', { origin: 'https://evil.example' }), fakeFetch);
  assert.equal(other.headers.get('Access-Control-Allow-Origin'), 'https://afg-design.github.io');   // browsers block it
});

test('FPL down: says so', async () => {
  const r = await handle(req('/entry/123/'), async () => { throw new Error('down'); });
  assert.equal(r.status, 502);
});
