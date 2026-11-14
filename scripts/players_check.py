"""Players table check (FL-156 idea 2): the fixed player column and the fixed header, at ten widths.

    python3 scripts/players_check.py              # needs site/data.json (see "Run locally" in the README)
    python3 scripts/players_check.py --out shots  # also saves a screenshot per width (default: players-shots/)

Opens Players with every column switched on (so the table must scroll sideways at every width) at 320, 375, 390, 430,
768, 820, 1024, 1280, 1440 and 1920px, scrolls the table to its right-hand end and down, and fails if:
  - the whole page scrolls sideways (the table must scroll inside its own box);
  - the player column has moved off the left edge of the table box, or the header off its top (when the box scrolls);
  - the player column takes more than 75% of the table box's width (no room for the stats; at 320px it once took 100%);
  - the top-left "Player" heading isn't on top where the fixed column and fixed header cross (with the page scrolled so
    the table's top sits just under the app's top bar, where you'd read it);
  - a player's compare tick box or name button is covered by another cell (it must be the element under its centre);
  - the "in your squad" edge is missing from a squad player's name cell;
  - Tab doesn't reach a player's name button, or it lands out of view.
Missing input fails loudly: no site/data.json or site/data-extra.json exits 2 before any check runs.
Needs Python Playwright (pre-installed in Claude sessions; elsewhere pip install playwright).
"""
import argparse, functools, http.server, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
WIDTHS = [320, 375, 390, 430, 768, 820, 1024, 1280, 1440, 1920]
ALL_COLS = ["team", "pos", "price", "form", "pts", "xg", "xa", "xgi90_4", "own", "t10k", "nailed", "xmin", "xp1", "xp5", "val", "pc"]

PROBE = """() => {
  const out = [], box = document.querySelector('.explorer .tablebox');
  if (!box) return ['no Players table box'];
  const de = document.documentElement;
  if (de.scrollWidth > innerWidth + 1) out.push(`page scrolls sideways (${de.scrollWidth}px wide in ${innerWidth}px)`);
  if (box.scrollWidth <= box.clientWidth + 1) out.push('note: table fits without sideways scroll');
  // read it where you would: the table's top just under the app's top bar (which stays on screen). Scrolling the page
  // further hides the headings under that bar, because they stay fixed inside the table box, not the page (FL-130)
  const bar = Math.max(0, ...[...document.querySelectorAll('.topbar')].map(e => e.getBoundingClientRect().bottom));
  scrollBy(0, box.getBoundingClientRect().top - bar - 4);
  box.scrollLeft = box.scrollWidth;
  const vert = box.scrollHeight > box.clientHeight + 1;
  if (vert) box.scrollTop = 300;
  const b = box.getBoundingClientRect();
  const th = box.querySelector('thead th.sticky-col'), row = box.querySelector('tbody tr:nth-child(3)');
  const td = row.querySelector('td.sticky-col'), r = td.getBoundingClientRect(), h = th.getBoundingClientRect();
  if (Math.abs(r.left - b.left) > 1.5) out.push(`player column moved ${Math.round(r.left - b.left)}px from the box's left edge`);
  // the fixed column must leave room for the stats: wider than the box, it can't stay pinned and hides every stat
  if (r.width > 0.75 * box.clientWidth) out.push(`player column is ${Math.round(r.width)}px of a ${box.clientWidth}px box: no room for the stats beside it`);
  if (vert && Math.abs(h.top - b.top) > 1.5) out.push(`header moved ${Math.round(h.top - b.top)}px from the box's top`);
  const at = (x, y) => document.elementFromPoint(x, y);
  const hit = at(h.left + h.width / 2, h.top + h.height / 2);
  if (!th.contains(hit)) out.push(`top-left heading covered by ${hit && hit.tagName}.${hit && (hit.closest('[class]') || hit).className}`);
  for (const [sel, name] of [['input[data-cmp]', 'compare tick box'], ['button.pname', 'name button']]) {
    const el = td.querySelector(sel); if (!el) { out.push('no ' + name); continue; }
    const e = el.getBoundingClientRect(), x = e.left + e.width / 2, y = e.top + e.height / 2;
    if (y < b.top || y > b.bottom) continue;   // scrolled out of the box vertically
    const u = at(x, y);
    if (!(el === u || el.contains(u) || (u && u.closest('label') && u.closest('label').contains(el)))) out.push(`${name} covered by ${u && u.tagName}.${u && u.className}`);
  }
  const mine = box.querySelector('tr.mine td.sticky-col');
  if (mine && !/inset/.test(getComputedStyle(mine).boxShadow)) out.push('squad edge missing on a squad player');
  return out;
}"""
TAB = """() => { const box = document.querySelector('.explorer .tablebox'); const b = box.getBoundingClientRect();
  const a = document.activeElement; if (!a || !a.matches('button.pname')) return 'Tab landed on ' + (a && a.tagName + '.' + a.className);
  const r = a.getBoundingClientRect(); return r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= 0 && r.bottom <= innerHeight + 1 ? '' : 'focused name out of view'; }"""


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(SITE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="players-shots"); a = ap.parse_args()
    for f in ("data.json", "data-extra.json"):
        if not (SITE / f).exists():
            print(f"players_check: site/{f} is missing; build first (see README, Run locally)"); sys.exit(2)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    httpd, url = serve(); fails = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in WIDTHS:
            ctx = b.new_context(viewport={"width": w, "height": 900}, service_workers="block")
            ctx.add_init_script("try{localStorage.setItem('fpl.cols', JSON.stringify(%s))}catch(e){}" % ALL_COLS)
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(url + "#players"); pg.wait_for_selector(".explorer .tablebox", timeout=20000)
            probs = [x for x in pg.evaluate(PROBE) if not x.startswith("note:")] + errs
            pg.screenshot(path=str(out / f"players-{w}.png"))
            # keyboard: Tab from the search box until a name button has focus (at most 60 presses)
            pg.focus("#q")
            for _ in range(60):
                pg.keyboard.press("Tab")
                if pg.evaluate("() => document.activeElement && document.activeElement.matches('button.pname')"):
                    break
            t = pg.evaluate(TAB)
            if t:
                probs.append(t)
            print(("FAIL" if probs else "ok  "), f"{w}px", "; ".join(probs))
            fails += [f"{w}px: {x}" for x in probs]
            ctx.close()
        b.close()
    httpd.shutdown()
    if fails:
        print(f"\n{len(fails)} problem(s)."); sys.exit(1)
    print(f"\nPlayer column and header stay fixed at all {len(WIDTHS)} widths; nothing covers the tick boxes or names; the page never scrolls sideways.")


if __name__ == "__main__":
    main()
