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
  - Homepage switch: Next deadline / Current GW keeps your plan, lineup and captain choices untouched, remembers the
    view you picked (but not the first-visit default), opens on Current GW only while FPL says a gameweek is under
    way, and the tabs work from the keyboard. In a finished gameweek Current GW shows FPL's own points.
  - Transfer paths (Planner): every row's Net xP is its cells minus 4 per hit, taken once, and vs Hold is Net minus
    Hold's; Hold has no hits; a free-transfer path has none and a paid one exactly -4; bank uses selling prices, not
    market prices; an over-budget path is flagged and can't be used; Use plan gives Your plan the same total and marks
    the row active; 3 and 6 GW horizons; selecting cells never changes saved paths; paths from an older squad show no
    totals until recalculated; a missing strategy shows no numbers; Optimise makes a new path without touching the
    others, and an impossible one fails with a reason and changes nothing.
  - Lineup style (Cards | Kits): Cards by default and when storage is blocked; the choice persists across pages and a
    reload; switching keeps the plan, gameweek and focus; the bench reads GK, 1, 2, 3; in Current GW the captain's
    actual points carry the armband once (never doubled again); one difficulty chip per fixture (two in a double, "No
    match" in a blank); the three-week run only in the Planner; prices only in Your plan, matching the selling price;
    "×2" only on the projected captain.
  - Set-piece tags: Pens / 2nd on pens / Corners / FKs from FPL's taker order show on player lists; no duty, no tag.
  - News text: FPL's injury note in the Planner's transfer reasons is shown as text, never read as HTML.
  - Squad uplift (K1): 'With your plan' is the squad after its moves, scored like the rating; no moves = same.
  - One confidence scale (U1): Home's decision cards use only Strong / Marginal / Coin flip, plus a Field's pick tag.
  - Move reason (U2): a planned move on Home's Transfers card has a one-line reason (xP over the plan, money).
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


# Timing-safe helpers for the focus checks. The app re-draws a view and then moves focus, and background work after load
# (plan sync, player detail) can re-draw once more, so a check reads focus by waiting up to `ms` for it rather than
# looking once. It still fails if focus never arrives.
def wait_true(page, js, ms=3000):
    try:
        page.wait_for_function(js, timeout=ms)
        return True
    except Exception:
        return False


# the plan as saved, without its save time: a background save of the same plan isn't a change
PLAN_JS = "JSON.stringify((({ updated, ...r }) => r)(sbState()))"


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


def check_home(browser, url):
    """The homepage's two views share one plan and never change it; the view choice is remembered."""
    out = []
    ctx = browser.new_context(service_workers="block")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"homepage uncaught: {e}"))
    page.goto(f"{url}#week")
    page.wait_for_selector(".home", timeout=20000)
    page.wait_for_load_state("networkidle")
    want = page.evaluate("gwInProgress() ? 'current' : 'next'")
    if page.evaluate("S.home") != want:
        out.append(f"first visit opened {page.evaluate('S.home')}, expected {want} (gameweek in progress: {want == 'current'})")
    if page.evaluate("localStorage.getItem('fpl.home')") is not None:
        out.append("the first-visit default was stored as if you had picked it")
    # a hand-made plan with a captain choice, then switch back and forth
    before = page.evaluate("""() => {
      const g = D.meta.next_gw, sq = squadAt(g), out = sq.find(i => P[i].pos === "MID");
      const inn = D.players.filter(p => p.pos === "MID" && !sq.includes(p.id) && p.price <= P[out].price).sort((a, b) => b.price - a.price)[0].id;
      editPlan(() => { SB.moves = SB.moves.filter(m => m.gw !== g); SB.moves.push({ gw: g, out, in: inn }); });
      const xi = myTeam().xi; setOv(g, o => { o.cap = xi[xi.length - 1]; });
      render();
      return JSON.stringify((({ updated, ...r }) => r)(sbState()));
    }""")
    page.click("#hometab-current")
    page.wait_for_selector('.home-current')
    page.wait_for_selector('#hometab-current[aria-selected="true"]')
    page.press("#hometab-current", "ArrowLeft")   # focuses the tab and presses in one step, so a re-draw can't slip between
    page.wait_for_selector(".home-next")
    if not wait_true(page, "document.activeElement && document.activeElement.id === 'hometab-next'"):
        out.append("arrow key switched the view but focus didn't follow the tab")
    if page.evaluate(PLAN_JS) != before:
        out.append("switching views changed the plan, lineup or captain choices")
    if page.evaluate("JSON.parse(localStorage.getItem('fpl.home'))") != "next":
        out.append("the view you picked wasn't remembered")
    if "your active draft" not in page.inner_text(".hero").lower():
        out.append("a hand-edited plan isn't labelled as your draft")
    page.reload()
    page.wait_for_selector(".home")
    if page.evaluate("S.home") != "next":
        out.append("after a reload the remembered view wasn't used")
    if page.evaluate(PLAN_JS) != before:
        out.append("the plan didn't survive a reload")
    # finished gameweek: Current GW shows FPL's points, not a recomputed total
    fin = page.evaluate("D.meta.cur_finished && D.live && D.live.gw === D.meta.cur_gw ? D.live.points : null")
    if fin is not None:
        page.click("#hometab-current")
        page.wait_for_selector(".home-current")
        if not page.inner_text(".hero h1").lower().startswith(f"{fin} points"):
            out.append(f"finished gameweek: hero doesn't show FPL's {fin} points")
    ctx.close()
    return out + errs


TPATHS = r"""async () => {
  const out = [], near = (a, b) => Math.abs(a - b) < 1e-6;
  setDrafts([]); setPlan([], "custom"); SB.ov = {}; S.mode = "balanced"; setHorizon(5);
  const g = PG[0], g2 = PG[1], sq = squadAt(g), bank = D.manager.bank;
  const best = (pos, not, cap) => D.players.filter(p => p.pos === pos && !not.includes(p.id) && p.ok !== false && p.price <= cap + 1e-9).sort((a, b) => xpFrom(b.id, g, 5) - xpFrom(a.id, g, 5))[0];
  // a player you own whose selling price differs from his market price, if there is one
  const sv = D.squad.find(s => Math.abs(s.sell - P[s.id].price) > 0.05) || D.squad.find(s => P[s.id].pos !== "GKP");
  const inn = best(P[sv.id].pos, sq, sv.sell + bank);
  const free = [{ gw: g, out: sv.id, in: inn.id }];
  const sq2 = sq.map(i => i === sv.id ? inn.id : i), used = [...sq2], outs = sq2.filter(i => P[i].pos === "DEF" && i !== inn.id).slice(0, 3);
  const paid = [...free, ...outs.map(o => { const b = best("DEF", used, sellPrice(o)); used.push(b.id); return { gw: g2, out: o, in: b.id }; })];
  const rich = D.players.filter(p => p.pos === "FWD" && !sq.includes(p.id)).sort((a, b) => b.price - a.price)[0];
  const cheapF = sq.filter(i => P[i].pos === "FWD").sort((a, b) => sellPrice(a) - sellPrice(b))[0];
  const broke = [{ gw: g, out: cheapF, in: rich.id }];
  setDrafts([{ id: "free", name: "Free", moves: free, ov: {}, mode: "balanced" }, { id: "paid", name: "Paid", moves: paid, ov: {}, mode: "balanced" },
             { id: "broke", name: "Broke", moves: broke, ov: {}, mode: "balanced" }]);
  let rows = tpRows();
  const hold = rows[0], R = k => rows.find(r => r.key === k);
  if (hold.sc.weeks.some(w => w.hits)) out.push("Hold has a hit");
  rows.filter(r => r.sc).forEach(r => {
    const sum = r.sc.weeks.reduce((a, w) => a + w.team.pts, 0), hits = r.sc.weeks.reduce((a, w) => a + w.hits, 0);
    if (!near(r.sc.tot, sum - 4 * hits)) out.push(`${r.name}: Net ${r.sc.tot} isn't the cells ${sum} minus 4 x ${hits} hits`);
    if (r.sc.weeks.length !== PG.length) out.push(`${r.name}: ${r.sc.weeks.length} cells for ${PG.length} GWs`);
  });
  const fr = R("d:free"), pd = R("d:paid"), bk = R("d:broke");
  if (fr.sc.weeks.some(w => w.hits)) out.push("free-transfer path took a hit");
  const pw = pd.sc.weeks.find(w => w.gw === g2);
  if (!(pw.n === 3 && pw.hits === 1)) out.push(`paid path GW${g2}: ${pw.n} moves, ${pw.hits} hits (expected 3 moves, 1 hit)`);
  if (!near(pd.sc.tot, pd.sc.weeks.reduce((a, w) => a + w.team.pts, 0) - 4)) out.push("paid path: the hit isn't taken exactly once");
  const want = Math.round((bank + sv.sell - inn.price) * 10) / 10, got = fr.sc.weeks[0].bank;
  if (!near(got, want)) out.push(`bank after selling ${P[sv.id].name}: ${got}, expected ${want} from his selling price ${sv.sell} (market ${P[sv.id].price})`);
  if (!bk.problems.length) out.push(`over-budget path (${P[rich.id].name} for ${P[cheapF.id].name}) isn't flagged`);
  // the table's own text: the gain column is Net minus Hold
  TP.sel = "hold"; TP.gw = null; S.pview = "compare"; setView("planner");
  document.querySelectorAll(".tp-row").forEach(tr => {
    const cells = tr.querySelectorAll("td"); if (cells.length < PG.length + 3) return;
    const net = +cells[PG.length].textContent, gain = cells[PG.length + 1].textContent.trim();
    if (gain === "—") return;
    const v = +gain.replace("−", "-").replace("±", "");
    if (Math.abs(v - (net - hold.sc.tot)) > 0.051) out.push(`row "${tr.querySelector(".tp-nm").textContent.trim()}": vs Hold ${gain} but Net ${net} − Hold ${hold.sc.tot.toFixed(1)}`);
  });
  // selecting cells and rows never changes saved paths
  const before = JSON.stringify(getDrafts());
  document.querySelector('[data-tpcell="d:paid|' + g2 + '"]').click();
  document.querySelector('[data-tprow="d:free"]').click();
  document.querySelector('[data-tpcell="hold|' + g + '"]').click();
  if (JSON.stringify(getDrafts()) !== before) out.push("selecting cells changed the saved paths");
  if (!document.querySelector(".tp-strip")) out.push("selecting a cell didn't open the detail strip");
  // an invalid path can't be used
  const planBefore = JSON.stringify(SB.moves);
  document.querySelector('[data-tpuse="d:broke"]').click();
  if (JSON.stringify(SB.moves) !== planBefore) out.push("an over-budget path became the active plan");
  // Use plan: Your plan shows the same total, and the row is marked active
  for (const k of ["m:balanced", "d:paid", "m:chase", "d:free", "hold"]) {
    const r = tpRows().find(x => x.key === k); if (!r || !r.sc) continue;
    const b = document.querySelector(`[data-tpuse="${k}"]`); if (!b) { out.push(`${k}: no Use plan button`); continue; }
    b.click();
    if (k === "hold") {   // clearing moves takes a second tap
      if (!SB.moves.length) { out.push("Clear my plan cleared the moves without asking"); }
      document.querySelector('[data-tpuse="hold"]').click();
    }
    const a = scoreMoves(SB.moves).tot, row = tpRows().find(x => x.key === k);
    if (!near(a, r.sc.tot)) out.push(`Use plan on ${r.name}: Your plan totals ${a.toFixed(2)}, the table ${r.sc.tot.toFixed(2)}`);
    if (!row.active) out.push(`Use plan on ${r.name}: row isn't marked active`);
    if (!sameMoves(myTeam().score.weeks.length ? SB.moves : [], r.moves)) out.push(`Use plan on ${r.name}: This week doesn't follow it`);
  }
  // a saved path whose Net has moved by 0.5+ since it was saved is flagged; within 0.5 it isn't
  const ds0 = tpIds(getDrafts()), fi = ds0.findIndex(d => d.id === "free");
  ds0[fi] = { ...tpStamp(ds0[fi]) }; setDrafts(ds0);
  if (tpRows().find(r => r.key === "d:free").moved) out.push("a path saved on this forecast is flagged as moved");
  ds0[fi] = { ...ds0[fi], net: ds0[fi].net + 0.6 }; setDrafts(ds0);
  if (!tpRows().find(r => r.key === "d:free").moved) out.push("a path whose Net moved by 0.6 isn't flagged");
  // editing a saved path in Your plan: changes can be saved back to it
  setView("planner"); S.pview = "compare"; render();
  document.querySelector('[data-tpuse="d:free"]').click();
  S.pview = "edit"; render();
  if (!document.querySelector(".tp-editbar")) out.push("Your plan doesn't say which saved path it's editing");
  editPlan(() => SB.moves.splice(0, 1)); render();
  document.querySelector("[data-tpesave]")?.click();
  if (getDrafts().find(d => d.id === "free").moves.length !== 0) out.push("Save changes to path didn't save the edit back");
  S.pview = "compare"; tpEditing(null); setView("planner");
  // horizons
  for (const h of [3, 6]) { if (h > GWS.length) continue; setHorizon(h); const rr = tpRows(); if (rr.filter(r => r.sc).some(r => r.sc.weeks.length !== PG.length)) out.push(`${h}-GW horizon: rows don't all have ${PG.length} cells`); }
  setHorizon(5);
  // a path made for an older squad: no totals until recalculated
  const oldKey = `fpl.sb.${D.meta.team_id}.${D.meta.next_gw - 1}.1-2-3.drafts`;
  store.set(oldKey, [{ name: "Old", moves: [{ gw: D.meta.next_gw - 1, out: 1, in: 2 }, ...free], ov: {}, mode: "balanced" }]);
  setDrafts(getDrafts().filter(d => d.id !== "broke"));
  rows = tpRows(); const old = rows.find(r => r.kind === "old");
  if (!old) out.push("a path from an older squad wasn't shown"); else if (old.sc) out.push("a path from an older squad shows totals");
  setView("planner");
  document.querySelector('[data-tprecalc]')?.click();
  const rec = getDrafts().find(d => d.name === "Old");
  if (!rec) out.push("recalculating an older path didn't add it"); else if (rec.moves.length !== 1) out.push(`recalculated path kept ${rec.moves.length} moves, expected 1 (the past-GW move dropped)`);
  if ((store.get(oldKey) || []).length) out.push("the older path wasn't removed after recalculating");
  // missing strategy: no numbers in its place
  const keep = {}; Object.keys(D.plans).filter(k => k.startsWith("chase_")).forEach(k => { keep[k] = D.plans[k]; delete D.plans[k]; });
  _pv = { key: "", res: {} };
  const ch = tpRows().find(r => r.key === "m:chase");
  if (!ch || ch.sc || !ch.missing) out.push("a strategy with no plan still shows numbers");
  Object.assign(D.plans, keep); _pv = { key: "", res: {} };
  // Optimise: a new path, others untouched; an impossible one fails and changes nothing
  setDrafts(getDrafts().slice(0, 1)); TP.sel = "hold"; TP.mode = "balanced";
  const keepPaths = JSON.stringify(getDrafts());
  await tpOptimise();
  const after = getDrafts();
  if (after.length !== 2 || JSON.stringify(after.slice(0, 1)) !== keepPaths) out.push(`Optimise from Hold: ${TP.msg}`);
  const club = D.players.filter(p => !sq.includes(p.id) && p.team === D.players.find(q => !sq.includes(q.id)).team).slice(0, 4).map(p => p.id);
  const rulesKeep = JSON.parse(JSON.stringify(SB.rules));
  SB.rules.locked = club; TP.sel = "hold";
  const keep2 = JSON.stringify(getDrafts());
  await tpOptimise();
  if (!/^Optimise failed/.test(TP.msg)) out.push(`impossible locks: expected a failure message, got "${TP.msg}"`);
  if (JSON.stringify(getDrafts()) !== keep2) out.push("a failed Optimise changed the saved paths");
  SB.rules = rulesKeep; store.set(oldKey, null); setDrafts([]);
  return out;
}"""


def check_tpaths(browser, url):
    ctx = browser.new_context(service_workers="block")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"transfer paths uncaught: {e}"))
    page.goto(f"{url}#planner")
    page.wait_for_selector(".view-planner", timeout=20000)
    try:
        out = page.evaluate(TPATHS)
    except Exception as e:
        out = [f"transfer paths check crashed: {e}"]
    ctx.close()
    return out + errs


def check_lineup(browser, url):
    out = []
    ctx = browser.new_context(service_workers="block")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(f"lineup uncaught: {e}"))
    page.goto(f"{url}#week")
    page.wait_for_selector(".home")
    page.wait_for_load_state("networkidle")
    if not page.locator(".pitchwrap.lu-cards").count():
        out.append("lineup doesn't default to Cards")
    view = "JSON.stringify([" + PLAN_JS + ", SB.gw, S.home])"
    before = page.evaluate(view)
    page.click('[data-lineup="kits"]')
    page.wait_for_selector(".pitchwrap.lu-kits")
    if not wait_true(page, "document.activeElement?.dataset.lineup === 'kits'"):
        out.append("focus didn't stay on the Kits button")
    if page.evaluate(view) != before:
        out.append("switching lineup style changed the plan or view")
    slots = page.evaluate("[...document.querySelectorAll('.lu-bench .lu-slot')].map(x => x.textContent)")
    if slots != ["GK", "1", "2", "3"]:
        out.append(f"bench slots read {slots}, expected GK, 1, 2, 3")
    chk = page.evaluate("""() => {
      const out = [], g = D.meta.next_gw, t = myTeam(), card = id => document.querySelector(`.view-week .pitch [data-p="${id}"]`);
      t.xi.forEach(i => { const n = fxFor(P[i].team, g).length, c = card(i).querySelectorAll('.lu-sub .fdr').length;
        if (c !== Math.max(1, n)) out.push(`${P[i].name}: ${c} fixture chips for ${n} fixtures`); });
      if (document.querySelector('.view-week .lu-run, .view-week .lu-price')) out.push("Home shows the Planner's run or prices");
      const x2 = [...document.querySelectorAll('.view-week .lu-x')].map(e => e.closest('[data-p]').dataset.p);
      if (x2.length !== 1 || +x2[0] !== t.cap) out.push(`×2 shown on ${x2.length} cards, expected only the captain`);
      // a double and a blank
      const a = t.xi.find(i => P[i].pos !== 'GKP'), b = t.xi.find(i => P[i].team !== P[a].team && P[i].pos !== 'GKP');
      const keepA = T[P[a].team].fx[g], keepB = T[P[b].team].fx[g];
      T[P[a].team].fx[g] = []; T[P[b].team].fx[g] = [...keepB, { opp: Object.keys(T).map(Number).find(x => x !== P[b].team && x !== P[a].team), home: false, fdr: 4 }];
      render();
      if (!/No match/.test(card(a).querySelector('.lu-sub').textContent)) out.push("a blank gameweek doesn't say No match");
      if (card(b).querySelectorAll('.lu-sub .fdr').length !== 2) out.push("a double gameweek doesn't show two chips");
      T[P[a].team].fx[g] = keepA; T[P[b].team].fx[g] = keepB; render();
      return out; }""")
    out += chk
    page.evaluate("() => { S.pview = 'mine'; setView('planner'); }")
    page.wait_for_selector(".view-planner .pitchwrap")
    if not page.locator(".view-planner .lu-run").count() or page.locator(".view-planner .lu-price").count():
        out.append("My team should show the run but no prices")
    page.evaluate("() => { S.pview = 'edit'; setView('planner'); }")
    page.wait_for_selector(".view-planner .lu-price")
    bad = page.evaluate("""() => [...document.querySelectorAll('.view-planner .lu-pc')].filter(c => {
      const id = +(c.dataset.sbp || c.dataset.p), owned = D.squad.some(s => s.id === id), want = owned ? `sells ${money(sellPrice(id))}` : money(P[id].price);
      return c.querySelector('.lu-price')?.textContent !== want; }).map(c => c.getAttribute('aria-label').split(',')[0])""")
    if bad:
        out.append(f"Your plan prices don't match the selling-price rule: {bad[:3]}")
    page.wait_for_selector(".view-planner .pitchwrap")
    if not page.locator(".view-planner .pitchwrap.lu-kits").count():
        out.append("Kits didn't carry over to the Planner")
    page.reload()
    page.wait_for_selector(".pitchwrap")
    if not page.locator(".pitchwrap.lu-kits").count():
        out.append("Kits wasn't remembered after a reload")
    # Current GW: the captain's number is his points times the armband, once
    page.evaluate("() => { S.home = 'current'; setView('week'); }")
    page.wait_for_selector(".home-current")
    cap = page.evaluate("""() => { const s = liveState(); if (!s) return null; const r = s.capOut ? s.vice : s.cap; if (!r) return null;
      const el = document.querySelector(`.pitch [data-p="${r.id}"] .xp`); return el ? [el.textContent, r.live, s.mult(r)] : null; }""")
    if page.locator(".home-current .lu-x").count():
        out.append("Current GW marks ×2 on a number that already includes the armband")
    if cap and cap[0] not in ("–", str(cap[1] * cap[2])):
        out.append(f"captain card shows {cap[0]}, expected {cap[1]} x {cap[2]} = {cap[1] * cap[2]}")
    ctx.close()
    # storage blocked: Cards, no error
    ctx = browser.new_context(service_workers="block")
    ctx.add_init_script("Storage.prototype.getItem = () => { throw new Error('blocked'); }; Storage.prototype.setItem = () => { throw new Error('blocked'); };")
    page = ctx.new_page()
    page.on("pageerror", lambda e: errs.append(f"lineup (storage blocked) uncaught: {e}"))
    page.goto(f"{url}#week")
    page.wait_for_selector(".home")
    page.wait_for_load_state("networkidle")
    if not page.locator(".pitchwrap.lu-cards").count():
        out.append("with storage blocked the lineup isn't Cards")
    page.click('[data-lineup="kits"]')
    if not page.locator(".pitchwrap.lu-kits").count():
        out.append("with storage blocked, Kits doesn't switch for the visit")
    ctx.close()
    return out + errs


def check_sp_tags(page):
    """Set-piece tags (S4): FPL's taker order shows as one tag on player lists, even where only 2 other tags fit."""
    r = page.evaluate("""() => {
      const tagText = p => { const d = document.createElement("div"); d.innerHTML = playerTags(p, 2); return d.textContent; };
      const find = f => D.players.find(f);
      const cases = [
        [find(p => p.sp?.pen === 1), "Pens"], [find(p => p.sp?.pen === 2), "2nd on pens"],
        [find(p => p.sp?.cor === 1), "Corners"], [find(p => p.sp?.fk === 1), "FKs"]];
      const none = find(p => !p.sp || (!p.sp.pen && !p.sp.cor && !p.sp.fk));
      return { cases: cases.filter(([p]) => p).map(([p, want]) => ({ name: p.name, want, got: tagText(p) })),
               none: none ? { name: none.name, got: tagText(none) } : null,
               missing: cases.filter(([p]) => !p).map(([, w]) => w) };
    }""")
    fails = [f"Set-piece tag: {c['name']} should show '{c['want']}' (tags: {c['got'] or 'none'})"
             for c in r["cases"] if c["want"] not in c["got"]]
    if r["none"] and any(w in r["none"]["got"] for w in ("Pens", "Corners", "FKs")):
        fails.append(f"Set-piece tag: {r['none']['name']} has no FPL duty but shows one ({r['none']['got']})")
    if r["missing"]:
        print(f"  (set-piece tags: no player in this build for {', '.join(r['missing'])}, not checked)")
    return fails


def check_news_escaped(page):
    """FPL's news note is shown as text, never read as HTML, in the Planner's transfer reasons (whyOut)."""
    r = page.evaluate("""() => {
      const p = D.players.find(x => P[x.id]) , keep = { st: p.status, news: p.news };
      p.status = "d"; p.news = '<img src=x data-bad="1">Knock & <b>doubt</b>';
      const html = whyOut(p.id, PG[0]);
      const box = document.createElement("div"); box.innerHTML = html;
      Object.assign(p, { status: keep.st, news: keep.news });
      return { tags: box.querySelectorAll("img, b").length, text: box.textContent };
    }""")
    fails = []
    if r["tags"]:
        fails.append(f"News text: the note was read as HTML in transfer reasons ({r['tags']} tags made)")
    if "<img" not in r["text"] or "Knock & " not in r["text"]:
        fails.append(f"News text: the note wasn't shown as written ({r['text'][:80]})")
    return fails


def check_uplift(page):
    """K1: the squad rating's "With your plan" figure is the squad after the plan's moves, scored like the rating
    (best XI + captain, minus 4 a hit), and with no moves it equals the squad as it stands."""
    r = page.evaluate("""() => {
      const keep = SB.moves.slice(), out = {};
      SB.moves = []; RATE.key = ""; const a = squadRatingData();
      out.none = a ? { same: a.plan.score === a.score && Math.abs(a.plan.pts - a.mine) < 1e-9, moves: a.plan.moves.length } : null;
      const rec = recommendedPlan();
      const mv = rec ? planMoves(D.plans[rec]) : [];
      SB.moves = mv; RATE.key = ""; const b = squadRatingData();
      if (b && mv.length) {
        const gws = b.gws; let ft = Math.min(5, D.manager.free_transfers), pts = 0;
        gws.forEach(g => { const n = mv.filter(m => m.gw === g).length, h = Math.max(0, n - ft); ft = n > ft ? 1 : Math.min(5, ft - n + 1);
          pts += bestXI(squadAt(g, mv), g, null).pts - 4 * h; });
        out.plan = { got: b.plan.pts, want: pts, moves: b.plan.moves.length };
        S.home = "next"; setView("week");
        out.shown = !!document.querySelector(".rate-uplift") && document.querySelector(".rating").textContent.includes(b.score + " → " + b.plan.score);
      }
      SB.moves = keep; RATE.key = ""; render();
      return out;
    }""")
    fails = []
    if r.get("none") and (not r["none"]["same"] or r["none"]["moves"]):
        fails.append(f"Uplift: with no moves the plan figure differs from the squad ({r['none']})")
    if r.get("plan"):
        if abs(r["plan"]["got"] - r["plan"]["want"]) > 1e-6:
            fails.append(f"Uplift: plan points {r['plan']['got']:.2f}, expected {r['plan']['want']:.2f}")
        if not r.get("shown"):
            fails.append("Uplift: the 'score to score with plan' line isn't shown on Home")
    else:
        print("  (uplift: the recommended plan has no moves this build; only the no-moves case checked)")
    return fails


def check_one_scale(page):
    """U1: every verdict on Home's decision cards and the Planner's captain table uses Strong / Marginal / Coin flip
    (whose pick it is, "Your pick" / "Re-plan's pick", is the only other label). "Field's pick" is a tag beside it."""
    r = page.evaluate("""() => {
      const SCALE = ["Strong", "Marginal", "Coin flip"], WHO = ["Your pick", "Re-plan's pick"];
      S.home = "next"; setView("week");
      const cards = [...document.querySelectorAll(".dcard h3 .pillwrap")].map(w => [...w.querySelectorAll(".pill")].map(x => x.textContent));
      const bad = cards.filter(p => !SCALE.includes(p[0]) || p.slice(1).some(t => t !== "Field's pick"));
      // the lineup verdict follows the bench gap on the 1 / 0.4 scale
      return { n: cards.length, bad, cards };
    }""")
    fails = []
    if r["n"] != 3:
        fails.append(f"One scale: expected 3 decision cards on Home, found {r['n']}")
    fails += [f"One scale: a Home card shows {b} (only Strong / Marginal / Coin flip, plus a Field's pick tag)" for b in r["bad"]]
    for gap, want in ((0.2, "Coin flip"), (0.5, "Marginal"), (1.2, "Strong")):
        got = page.evaluate(f"verdict({gap}, 1, 0.4).t")
        if got != want:
            fails.append(f"One scale: a {gap}-point lineup/captain gap reads {got}, expected {want}")
    return fails


def check_move_reason(page):
    """U2: each move planned for the next GW has a one-line reason on Home's Transfers card: the players' own xP over the
    plan length and the money, from your real selling price."""
    r = page.evaluate("""() => {
      const keep = { moves: SB.moves.slice(), src: SB.source, solved: SB.solved }, g = D.meta.next_gw, sq = squadAt(g);
      const out = sq.find(i => P[i].pos === "MID");
      const inn = D.players.filter(p => p.pos === "MID" && !sq.includes(p.id) && p.price <= sellPrice(out) + D.manager.bank).sort((a, b) => b.xp5 - a.xp5)[0].id;
      SB.moves = [{ gw: g, out, in: inn }]; SB.solved = null; S.home = "next"; setView("week");
      const li = document.querySelector(".dc-moves li .dc-why");
      const d = xpFrom(inn, g, PG.length) - xpFrom(out, g, PG.length), cash = Math.round((sellPrice(out) - P[inn].price) * 10) / 10;
      const res = { text: li ? li.textContent : null, want: [P[inn].name, sgn(d), P[out].name, cash > 0 ? "frees" : cash < 0 ? "costs" : "same money"] };
      Object.assign(SB, keep); render();
      return res;
    }""")
    if r["text"] is None:
        return ["Move reason: no one-line reason under a planned move on Home"]
    missing = [w for w in r["want"] if w not in r["text"]]
    return [f"Move reason: '{r['text']}' is missing {missing}"] if missing else []


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
                         ("free hit note", lambda: check_fh_note(page)),
                         ("set-piece tags", lambda: check_sp_tags(page)),
                         ("news text", lambda: check_news_escaped(page)),
                         ("squad uplift", lambda: check_uplift(page)),
                         ("one confidence scale", lambda: check_one_scale(page)),
                         ("move reason", lambda: check_move_reason(page))):
            got = fn()
            failures += got
            print(("✗ " if got else "✓ ") + name)
        failures += errs
        ctx.close()
        got = check_extra(browser, url)
        failures += got
        print(("✗ " if got else "✓ ") + "player detail")
        got = check_lineup(browser, url)
        failures += got
        print(("✗ " if got else "✓ ") + "lineup styles")
        got = check_tpaths(browser, url)
        failures += got
        print(("✗ " if got else "✓ ") + "transfer paths")
        got = check_home(browser, url)
        failures += got
        print(("✗ " if got else "✓ ") + "homepage views")
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
