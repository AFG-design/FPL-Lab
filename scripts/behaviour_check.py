"""Behaviour checks: planner interactions and offline recovery that the layout check doesn't exercise.

    python3 scripts/behaviour_check.py      # needs site/data.json and site/data-extra.json, like layout_check.py

Starts its own static server and a headless Chromium, then runs each check against the real site and data:
  - Re-plan with a ban on a player you own: must succeed and sell him (it used to fail with "No plan found").
  - Re-plan with a lock on a player you don't own: must succeed and buy him.
  - Re-plan with no locks or bans: must still succeed (regression guard for the two above).
  - Re-plan's lineups and captains are the ones shown for its plan (Balanced, and Chase/Play safe when the build has
    field ownership), and editing the plan clears them.
  - Vice-captain chosen with the captain left automatic: your vice must be used, and the captain must not be him.
  - Free Hit week: the Planner says plans start from the restored squad, and says nothing in a normal week.
  - Player detail: a data-extra.json from another build is never merged and ends in an error with Try again; one
    failed download is recovered by a retry.
  - Service worker: a 500 for data.json must not replace the good offline copy, and the page gets that copy back.

Missing input fails loudly: no site/data.json or site/data-extra.json exits 2 before any check runs. If the data has no
cheap enough player to lock (it always should), that check fails with the reason rather than being skipped.
Needs Python Playwright: pip install playwright && python3 -m playwright install chromium
"""
import functools, http.server, json, os, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent / "site"


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(SITE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


# Runs in the page. Sets the rules, runs Re-plan in Balanced mode and reports what came back.
REPLAN = """async ({ ban, lock }) => {
  SB.rules.banned = ban; SB.rules.locked = lock; SB.moves = []; S.mode = "balanced";
  await runReplan();
  return { msg: SOLVE.msg, moves: SB.moves.map(m => ({ out: m.out, in: m.in, gw: m.gw })) };
}"""


def check_replan(page):
    fails = []
    info = page.evaluate("""() => {
      const owned = D.squad.map(s => s.id), ok = new Set(owned);
      // an owned outfield player to ban; the cheapest available defender we don't own to lock (always affordable
      // by selling any defender)
      const ban = owned.find(i => P[i] && P[i].pos !== "GKP");
      const lock = D.players.filter(p => p.pos === "DEF" && !ok.has(p.id) && p.ok !== false).sort((a, b) => a.price - b.price)[0]?.id;
      return { ban, lock, banName: P[ban]?.name, lockName: P[lock]?.name };
    }""")
    if not info["ban"] or not info["lock"]:
        return [f"Re-plan: couldn't pick test players from this data ({info})"]

    r = page.evaluate(REPLAN, {"ban": [], "lock": []})
    if not r["msg"].startswith("Done"):
        fails.append(f"Re-plan with no rules: {r['msg']}")

    r = page.evaluate(REPLAN, {"ban": [info["ban"]], "lock": []})
    if not r["msg"].startswith("Done"):
        fails.append(f"Re-plan banning owned {info['banName']}: {r['msg']}")
    elif not any(m["out"] == info["ban"] for m in r["moves"]):
        fails.append(f"Re-plan banning owned {info['banName']}: he isn't sold ({r['moves']})")

    r = page.evaluate(REPLAN, {"ban": [], "lock": [info["lock"]]})
    if not r["msg"].startswith("Done"):
        fails.append(f"Re-plan locking non-owned {info['lockName']}: {r['msg']}")
    elif not any(m["in"] == info["lock"] for m in r["moves"]):
        fails.append(f"Re-plan locking non-owned {info['lockName']}: he isn't bought ({r['moves']})")

    # Re-plan's own lineups and captains are what's shown, in Balanced and in a strategy mode (needs field ownership)
    for mode in ("balanced", "chase", "safe"):
        r = page.evaluate("""async (mode) => {
          if (mode !== "balanced" && !fieldEO()) return { skip: true };
          SB.rules.banned = []; SB.rules.locked = []; SB.moves = []; SB.ov = {}; S.mode = mode;
          await runReplan();
          if (!SOLVE.msg.startsWith("Done")) return { msg: SOLVE.msg };
          const sc = scoreMoves(SB.moves), bad = [];
          sc.weeks.forEach(w => {
            const s = SB.solved?.[w.gw];
            if (!s) { bad.push(`GW${w.gw}: no solved lineup kept`); return; }
            const same = s.xi.length === w.team.xi.length && s.xi.every(i => w.team.xi.includes(i));
            if (!same || w.team.cap !== s.cap || !w.team.fromPlan) bad.push(`GW${w.gw}: shown XI/captain differ from Re-plan's`);
          });
          editPlan(() => {});                                   // any edit clears them
          const cleared = SB.solved === null && !scoreMoves(SB.moves).weeks.some(w => w.team.fromPlan);
          return { msg: SOLVE.msg, bad, cleared };
        }""", mode)
        if r.get("skip"):
            print(f"  (Re-plan lineups, {mode}: no field-ownership data in this build, not checked)")
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::warning title=Behaviour check::Re-plan lineups ({mode}) not checked: no field-ownership data")
            continue
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::notice title=Behaviour check::Re-plan lineups ({mode}) checked: shown XI and captain match the solver")
        if not r["msg"].startswith("Done"):
            fails.append(f"Re-plan lineups ({mode}): {r['msg']}")
            continue
        fails += [f"Re-plan lineups ({mode}): {b}" for b in r["bad"]]
        if not r["cleared"]:
            fails.append(f"Re-plan lineups ({mode}): editing the plan didn't clear Re-plan's lineups")

    page.evaluate("() => { SB.rules.banned = []; SB.rules.locked = []; SB.moves = []; SB.solved = null; S.mode = 'balanced'; }")
    return fails


def check_vice(page):
    r = page.evaluate("""() => {
      const g = GWS[0], ids = D.squad.map(s => s.id);
      const auto = bestXI(ids, g, {});
      const pick = auto.xi.find(i => i !== auto.cap && i !== auto.vice);       // a starter who is neither
      const a = bestXI(ids, g, { vice: pick });                                 // vice only, captain automatic
      const b = bestXI(ids, g, { vice: auto.cap });                             // vice = the model's own captain
      const c = bestXI(ids, g, { cap: auto.vice, vice: pick });                 // both chosen (worked before)
      return { auto, pick, a, b, c };
    }""")
    fails, auto, pick = [], r["auto"], r["pick"]
    if r["a"]["vice"] != pick or r["a"]["cap"] != auto["cap"]:
        fails.append(f"vice only: wanted C {auto['cap']} V {pick}, got C {r['a']['cap']} V {r['a']['vice']}")
    if r["b"]["vice"] != auto["cap"] or r["b"]["cap"] == auto["cap"]:
        fails.append(f"vice = model captain: wanted V {auto['cap']} and a different captain, got C {r['b']['cap']} V {r['b']['vice']}")
    if r["c"]["cap"] != auto["vice"] or r["c"]["vice"] != pick:
        fails.append(f"captain and vice: wanted C {auto['vice']} V {pick}, got C {r['c']['cap']} V {r['c']['vice']}")
    return [f"Vice-captain {f}" for f in fails]


def check_fh_note(page):
    """During a Free Hit week the Planner must say plans start from the restored squad (and stay quiet otherwise)."""
    r = page.evaluate("""() => {
      const keep = { v: S.view, pv: S.pview, fh: D.meta.fh_restored, pg: D.meta.picks_gw, sg: D.meta.squad_gw };
      const txt = () => document.querySelector(".view-planner")?.innerText || "";
      S.view = "planner"; S.pview = "mine";
      D.meta.fh_restored = false; render(); const off = txt();
      D.meta.fh_restored = true; D.meta.picks_gw = 10; D.meta.squad_gw = 9; render(); const on = txt();
      Object.assign(D.meta, { fh_restored: keep.fh, picks_gw: keep.pg, squad_gw: keep.sg }); S.view = keep.v; S.pview = keep.pv; render();
      return { off: off.includes("Free Hit active"), on: on.includes("Free Hit active in GW10") && on.includes("your GW9 team") };
    }""")
    fails = []
    if not r["on"]:
        fails.append("Free Hit note: missing from the Planner when the squad was restored")
    if r["off"]:
        fails.append("Free Hit note: shown when no Free Hit is active")
    return fails


def check_extra(browser, url):
    """Player detail (data-extra.json): a file from another build is never merged, a failed download is retried, and
    when every try fails Stats shows an error with Try again (not a blank or half-filled page)."""
    fails = []
    real = (SITE / "data-extra.json").read_text()
    built = json.loads((SITE / "data.json").read_text())["meta"]["built"]

    def run(handler, expect):
        ctx = browser.new_context(service_workers="block")
        ctx.add_init_script("window.__fastRetry = true")
        calls = []
        def route(r):
            calls.append(1)
            handler(r, len(calls))
        ctx.route("**/data-extra.json*", route)
        page = ctx.new_page()
        page.goto(f"{url}#stats")
        page.wait_for_function("() => typeof D !== 'undefined' && D && (EXTRA.ready || EXTRA.failed)", timeout=30000)
        got = page.evaluate("""() => ({ ready: EXTRA.ready, failed: EXTRA.failed,
            merged: Object.values(P).some(p => p.s_pts !== undefined),
            err: !!document.querySelector('#retryExtra') })""")
        ctx.close()
        return got, len(calls)

    old = json.loads(real); old["built"] = "2000-01-01T00:00:00+00:00"
    # 1) always from another build: never merged, ends in the error state with Try again
    got, n = run(lambda r, k: r.fulfill(status=200, content_type="application/json", body=json.dumps(old)), "failed")
    if got["ready"] or got["merged"]:
        fails.append(f"Detail: a file from another build was merged ({got})")
    if not got["failed"] or not got["err"]:
        fails.append(f"Detail: mismatched builds didn't end in an error with Try again ({got})")
    if n < 2:
        fails.append(f"Detail: mismatched file wasn't retried ({n} request)")
    # 2) one failed download, then the right file: retried and merged
    got, n = run(lambda r, k: r.fulfill(status=500, body="err") if k == 1 else r.fulfill(status=200, content_type="application/json", body=real), "ready")
    if not got["ready"] or not got["merged"] or got["failed"]:
        fails.append(f"Detail: one failed download wasn't recovered by a retry ({got}, {n} requests)")
    return fails


def check_sw(browser, url):
    ctx = browser.new_context(service_workers="allow")
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("() => navigator.serviceWorker.controller !== null", timeout=20000)
    page.evaluate("() => fetch('data.json?t=' + Date.now(), { cache: 'no-store' })")   # a good copy in the cache
    # the cache write happens after the response is handed back, so wait for it (up to 10 s)
    good = page.evaluate("""async () => {
      for (let n = 0; n < 50; n++) { const r = await caches.match('data.json'); if (r) return (await r.json()).meta.built; await new Promise(f => setTimeout(f, 200)); }
      return null;
    }""")
    fails = []
    if not good:
        fails.append("Service worker: no offline copy of data.json after a good load")
    # the server now fails; the service worker sees a 500 (routes apply to its requests too)
    ctx.route("**/data.json*", lambda route: route.fulfill(status=500, body="server error"))
    got = page.evaluate("async () => { const r = await fetch('data.json?t=' + Date.now(), { cache: 'no-store' }); return { s: r.status, built: r.ok ? (await r.json()).meta.built : null }; }")
    page.wait_for_timeout(1000)   # give a (wrong) cache write time to land before looking
    kept = page.evaluate("async () => { const r = await caches.match('data.json'); return r ? { s: r.status, built: r.ok ? (await r.json()).meta.built : null } : null; }")
    if good and (not kept or kept["s"] != 200 or kept["built"] != good):
        fails.append(f"Service worker: a 500 replaced the offline copy (now {kept})")
    if good and (got["s"] != 200 or got["built"] != good):
        fails.append(f"Service worker: a 500 wasn't answered from the offline copy (page got {got})")
    ctx.close()
    return fails


def main():
    missing = [f for f in ("data.json", "data-extra.json") if not (SITE / f).exists()]
    if missing:
        print(f"behaviour_check: site/{', site/'.join(missing)} missing; build first (python3 build.py TEAM_ID site/data.json)")
        sys.exit(2)
    httpd, url = serve()
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(service_workers="block")
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(f"uncaught: {e}"))
        page.goto(f"{url}#planner")
        page.wait_for_selector(".view-planner", timeout=20000)
        for name, fn in (("vice", lambda: check_vice(page)), ("replan", lambda: check_replan(page)),
                         ("free hit note", lambda: check_fh_note(page))):
            got = fn()
            failures += got
            print(("✗ " if got else "✓ ") + name)
        failures += errs
        ctx.close()
        got = check_extra(browser, url)
        failures += got
        print(("✗ " if got else "✓ ") + "player detail")
        got = check_sw(browser, url)
        failures += got
        print(("✗ " if got else "✓ ") + "service worker")
        browser.close()
    httpd.shutdown()
    if failures:
        print("\n".join(["", "Failures:"] + [f"  - {f}" for f in failures]))
        if os.environ.get("GITHUB_ACTIONS"):   # also as annotations, so they show on the PR's checks page
            for f in failures:
                print(f"::error title=Behaviour check::{f}")
        sys.exit(1)
    print("All behaviour checks passed.")


if __name__ == "__main__":
    main()
