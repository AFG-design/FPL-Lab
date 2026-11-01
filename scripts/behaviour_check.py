"""Behaviour checks: planner interactions and offline recovery that the layout check doesn't exercise.

    python3 scripts/behaviour_check.py      # needs site/data.json and site/data-extra.json, like layout_check.py

Starts its own static server and a headless Chromium, then runs each check against the real site and data:
  - Re-plan with a ban on a player you own: must succeed and sell him (it used to fail with "No plan found").
  - Re-plan with a lock on a player you don't own: must succeed and buy him.
  - Re-plan with no locks or bans: must still succeed (regression guard for the two above).
  - Vice-captain chosen with the captain left automatic: your vice must be used, and the captain must not be him.
  - Service worker: a 500 for data.json must not replace the good offline copy, and the page gets that copy back.

Missing input fails loudly: no site/data.json or site/data-extra.json exits 2 before any check runs. If the data has no
cheap enough player to lock (it always should), that check fails with the reason rather than being skipped.
Needs Python Playwright: pip install playwright && python3 -m playwright install chromium
"""
import functools, http.server, os, socketserver, sys, threading
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

    page.evaluate("() => { SB.rules.banned = []; SB.rules.locked = []; SB.moves = []; }")
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


def check_sw(browser, url):
    ctx = browser.new_context(service_workers="allow")
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("() => navigator.serviceWorker.controller !== null", timeout=20000)
    page.evaluate("() => fetch('data.json?t=' + Date.now(), { cache: 'no-store' })")   # a good copy in the cache
    good = page.evaluate("async () => { const r = await caches.match('data.json'); return r ? (await r.json()).meta.built : null; }")
    fails = []
    if not good:
        fails.append("Service worker: no offline copy of data.json after a good load")
    # the server now fails; the service worker sees a 500 (routes apply to its requests too)
    ctx.route("**/data.json*", lambda route: route.fulfill(status=500, body="server error"))
    got = page.evaluate("async () => { const r = await fetch('data.json?t=' + Date.now(), { cache: 'no-store' }); return { s: r.status, built: r.ok ? (await r.json()).meta.built : null }; }")
    page.wait_for_timeout(300)   # let any cache write finish
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
        for name, fn in (("vice", lambda: check_vice(page)), ("replan", lambda: check_replan(page))):
            got = fn()
            failures += got
            print(("✗ " if got else "✓ ") + name)
        failures += errs
        ctx.close()
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
