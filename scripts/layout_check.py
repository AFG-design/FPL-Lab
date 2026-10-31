"""Phone and desktop layout check: opens every screen at 390px and 1280px wide and fails on problems.

    python3 scripts/layout_check.py              # needs site/data.json (see "Run locally" in the README)
    python3 scripts/layout_check.py --out shots  # also where the screenshots go (default: layout-shots/)

Starts its own static server on a free port, so nothing else needs to be running. For each view listed in
VIEWS (site/js/core/state.js, so new screens are covered without editing this file) and each width it checks:
  - no JavaScript errors (uncaught exceptions or console.error);
  - no "This section couldn't be drawn" error card (the per-view error boundary in nav.js);
  - no sideways scroll of the whole page (wide tables scroll inside their own box, which is fine);
  - every file the page loads from this site exists (a 404 on a script, stylesheet or data file fails).
It saves a full-page screenshot of every view and width, so a reviewer can look without running anything.

Missing input fails loudly: no site/data.json or site/data-extra.json, or VIEWS not found in state.js, exits 2 before any check runs.
Files from other sites (e.g. kit images) are not this check's business; their failures are listed, not failed.

Needs Python Playwright: pip install playwright && python3 -m playwright install chromium
"""
import argparse, functools, http.server, re, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
WIDTHS = {"phone": (390, 844), "desktop": (1280, 900)}


def views():
    m = re.search(r"const VIEWS = \[([^\]]*)\]", (SITE / "js" / "core" / "state.js").read_text())
    if not m:
        sys.exit("layout_check: couldn't find `const VIEWS = [...]` in site/js/core/state.js")
    return re.findall(r'"([^"]+)"', m.group(1))


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(SITE))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="layout-shots")
    a = ap.parse_args()
    missing = [f for f in ("data.json", "data-extra.json") if not (SITE / f).exists()]
    if missing:
        print(f"layout_check: site/{', site/'.join(missing)} missing; build first (python3 build.py TEAM_ID site/data.json)")
        sys.exit(2)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    vs = views()
    httpd, url = serve()
    failures, external = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size, (w, h) in WIDTHS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, service_workers="block")
            for v in vs:
                page = ctx.new_page()
                errs = []
                page.on("pageerror", lambda e, errs=errs: errs.append(f"uncaught: {e}"))
                # "Failed to load resource" console lines duplicate the response check below, which tells this site's
                # files (fail) from other sites' (listed only), so they're skipped here.
                page.on("console", lambda m, errs=errs: errs.append(f"console.error: {m.text}")
                        if m.type == "error" and not m.text.startswith("Failed to load resource") else None)

                def on_response(r, errs=errs):
                    if r.status >= 400:
                        (errs.append(f"{r.status} {r.url[len(url) - 1:]}") if r.url.startswith(url) else external.add(f"{r.status} {r.url}"))
                page.on("response", on_response)
                page.on("requestfailed", lambda r: external.add(f"failed {r.url}") if not r.url.startswith(url) else None)

                page.goto(f"{url}#{v}")
                try:
                    page.wait_for_selector(f".view-{v}", timeout=20000)
                except Exception:
                    errs.append("view never rendered (.view-%s missing after 20 s)" % v)
                page.wait_for_timeout(800)   # late renders: kit images, extra data for some views
                if page.locator(".state.error").count():
                    errs.append("error card shown: " + page.locator(".state.error h2").first.inner_text())
                sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                if sw > cw + 1:
                    wide = page.evaluate("""cw => [...document.querySelectorAll('#app *')]
                        .filter(e => e.getBoundingClientRect().right > cw + 1 && !e.closest('.tablebox'))
                        .slice(0, 3).map(e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/).join('.') : ''))""", cw)
                    errs.append(f"page scrolls sideways: {sw}px content in a {cw}px window (widest: {', '.join(wide) or 'outside #app'})")
                page.screenshot(path=str(out / f"{v}-{size}.png"), full_page=True)
                status = "ok" if not errs else "FAIL"
                print(f"{status:4} {size:7} {v}")
                failures += [f"{v} @ {w}px: {e}" for e in errs]
                page.close()
            ctx.close()
        browser.close()
    httpd.shutdown()
    if external:
        print(f"\n{len(external)} requests to other sites failed (not counted as failures), e.g. {sorted(external)[0]}")
    print(f"\nScreenshots in {out}/")
    if failures:
        print(f"\n{len(failures)} problem(s):")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print(f"All {len(vs)} views fine at {' and '.join(f'{w}px' for w, _ in WIDTHS.values())}.")


if __name__ == "__main__":
    main()
