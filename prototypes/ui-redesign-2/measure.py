"""Measure the round-2 prototypes (and optionally a local copy of the live site) for the comparison scorecard.

    python3 prototypes/ui-redesign-2/measure.py [LIVE_SITE_DIR]

Prototype tooling only. For each concept, at 390x844 and 1440x900 in dark and light, it reports:
  header_px   where the first content starts below the header (phone; the sample-data strip is subtracted)
  small_text  visible text elements under 11px
  small_taps  visible buttons/links/inputs smaller than 24x24 px (WCAG 2.5.8)
  low_contrast visible text below AA (4.5:1, or 3:1 for large text) against its nearest solid background;
               text on gradients or images is skipped and counted as "skipped", never assumed to pass.
LIVE_SITE_DIR, if given, must be a copy of site/ with data.json and data-extra.json in it (the live site is not
fetched). Writes measurements.json next to this file.
"""
import functools, http.server, json, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCREENS = ["home", "planner", "players", "players/411", "fixtures", "rivals", "model", "model/health"]
LIVE_SCREENS = ["week", "planner", "players", "fixtures", "rivals", "model", "health"]

JS = r"""() => {
  const lum = c => { const m = c.match(/[\d.]+/g); if (!m) return null; const k = c.startsWith("color(") ? 1 : 255;   // color-mix() computes to color(srgb 0-1)
    const [r, g, b] = m.slice(0, 3).map(v => { v = v / k; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }); return { L: .2126 * r + .7152 * g + .0722 * b, a: m[3] == null ? 1 : +m[3] }; };
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && s.visibility !== "hidden" && +s.opacity > 0.05; };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e); if (s.backgroundImage !== "none") return "skip"; const c = lum(s.backgroundColor); if (c && c.a > 0.95) return c.L; } return lum(getComputedStyle(document.body).backgroundColor)?.L ?? 1; };
  let small = 0, low = 0, skipped = 0, n = 0;
  const texts = [...document.querySelectorAll("body *")].filter(e => [...e.childNodes].some(t => t.nodeType === 3 && t.textContent.trim()) && vis(e) && !e.closest(".sample,svg"));
  for (const e of texts) { n++; const s = getComputedStyle(e), fs = parseFloat(s.fontSize); if (fs < 11) small++;
    const fg = lum(s.color), bg = bgOf(e); if (bg === "skip" || !fg || fg.a < 0.95) { skipped++; continue; }
    const cr = (Math.max(fg.L, bg) + .05) / (Math.min(fg.L, bg) + .05), big = fs >= 24 || (fs >= 18.66 && +s.fontWeight >= 700);
    if (cr < (big ? 3 : 4.5)) low++; }
  const taps = [...document.querySelectorAll("button,a[href],input,select,[role=radio],[role=checkbox]")].filter(vis).filter(e => { const r = e.getBoundingClientRect(); return r.width < 24 || r.height < 24; }).length;
  const app = document.querySelector("#app"), strip = document.querySelector(".sample");
  const header = app ? Math.round(app.getBoundingClientRect().top + scrollY - (strip ? strip.getBoundingClientRect().height : 0)) : null;
  return { texts: n, small_text: small, low_contrast: low, skipped, small_taps: taps, header_px: header };
}"""


def serve(directory):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(directory)))
    threading.Thread(target=h.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{h.server_address[1]}"


def run(b, urls, w, h, theme, live):
    tot = {"texts": 0, "small_text": 0, "low_contrast": 0, "skipped": 0, "small_taps": 0, "header_px": None}
    for u in urls:
        ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
        if live:
            ctx.add_init_script(f"try{{localStorage.setItem('fpl.theme','{theme}')}}catch(e){{}}")
        pg = ctx.new_page()
        pg.goto(u)
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(1200 if live else 250)
        r = pg.evaluate(JS)
        for k in ("texts", "small_text", "low_contrast", "skipped", "small_taps"):
            tot[k] += r[k]
        if tot["header_px"] is None:
            tot["header_px"] = r["header_px"]
        ctx.close()
    return tot


def main():
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        host = serve(ROOT)
        for c in ["a-refined", "b-analytics", "c-interactive"]:
            for size, (w, h) in {"phone": (390, 844), "desktop": (1440, 900)}.items():
                for theme in ("dark", "light"):
                    urls = [f"{host}/prototypes/ui-redesign-2/{c}/index.html?theme={theme}#{s}" for s in SCREENS]
                    out[f"{c}/{size}/{theme}"] = run(b, urls, w, h, theme, False)
            print("measured", c)
        if len(sys.argv) > 1:
            live = serve(Path(sys.argv[1]))
            for size, (w, h) in {"phone": (390, 844), "desktop": (1440, 900)}.items():
                for theme in ("dark", "light"):
                    out[f"current/{size}/{theme}"] = run(b, [f"{live}/index.html#{s}" for s in LIVE_SCREENS], w, h, theme, True)
            print("measured current")
    (HERE / "measurements.json").write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        print(f"{k:28} {v}")


if __name__ == "__main__":
    main()
