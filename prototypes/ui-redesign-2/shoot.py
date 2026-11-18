"""Screenshot the round-2 UI redesign prototypes (prototype tooling only; nothing in site/ or CI uses this).

    python3 prototypes/ui-redesign-2/shoot.py [a-refined b-analytics c-interactive]

Serves the repo root on a free local port (the prototypes borrow fonts and club badges from site/ read-only; no other
network), opens each screen at phone (390x844) and desktop (1440x900) widths and saves WebP files to screenshots/.
Fails loudly (exit 1) on any JavaScript error, a failed or non-local request, or sideways page scroll, so a broken
prototype is never shot silently.
"""
import functools, http.server, io, socketserver, sys, threading
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "screenshots"
SCREENS = ["home", "planner", "players", "players/411", "fixtures", "rivals", "model", "model/health"]
LIGHT = ["home", "players", "players/411"]
EXTRA = {"c-interactive": ["home?state=palette", "players?state=compare"]}   # interactive states only C has
SIZES = {"phone": (390, 844), "desktop": (1440, 900)}


def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=h.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{h.server_address[1]}"


def save(png, path, size):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if size == "desktop":
        im = im.resize((1440, round(im.height * 1440 / im.width)), Image.LANCZOS)
    im.save(path, "WEBP", quality=80, method=6)


def name_of(s):
    s, _, q = s.partition("?")
    return s.replace("/411", "-detail").replace("/", "-") + (("-" + q.split("=")[1]) if q else "")


def main():
    concepts = sys.argv[1:] or ["a-refined", "b-analytics", "c-interactive"]
    OUT.mkdir(exist_ok=True)
    host, bad = serve(), []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for c in concepts:
            for size, (w, h) in SIZES.items():
                for theme in ("dark", "light"):
                    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, reduced_motion="reduce")
                    pg = ctx.new_page()
                    pg.on("pageerror", lambda e, c=c: bad.append(f"{c}: {e}"))
                    pg.on("console", lambda m, c=c: m.type == "error" and bad.append(f"{c}: console {m.text}"))
                    pg.on("request", lambda r, c=c: r.url.startswith(host) or r.url.startswith("data:") or bad.append(f"{c}: non-local request {r.url}"))
                    pg.on("response", lambda r, c=c: r.status >= 400 and bad.append(f"{c}: {r.status} {r.url}"))
                    screens = SCREENS + EXTRA.get(c, []) if theme == "dark" else LIGHT
                    for s in screens:
                        route, _, q = s.partition("?")
                        qs = f"theme={theme}" + (f"&{q}" if q else "")
                        pg.goto(f"{host}/prototypes/ui-redesign-2/{c}/index.html?{qs}#{route}")
                        pg.wait_for_load_state("networkidle")
                        pg.wait_for_timeout(300)
                        save(pg.screenshot(), OUT / f"{c}--{name_of(s)}--{size}--{theme}.webp", size)
                        if s == "home" and theme == "dark":
                            save(pg.screenshot(full_page=True), OUT / f"{c}--home-full--{size}--dark.webp", size)
                        sw = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
                        if sw[0] > sw[1]:
                            bad.append(f"{c} {s} {size}: page scrolls sideways ({sw[0]} > {sw[1]})")
                    ctx.close()
            print("shot", c)
    if bad:
        print("PROBLEMS:\n  " + "\n  ".join(sorted(set(bad))))
        sys.exit(1)


if __name__ == "__main__":
    main()
