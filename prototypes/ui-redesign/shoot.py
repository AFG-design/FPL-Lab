"""Screenshot the UI redesign prototypes (prototype tooling only; nothing in site/ or CI uses this).

    python3 prototypes/ui-redesign/shoot.py [a-refined b-analytics c-interactive]

Serves the repo root on a free local port (the prototypes borrow fonts and club badges from site/ read-only),
opens each screen at phone (390x844) and desktop (1440x900) widths and saves WebP files to screenshots/
(desktop downscaled to 1440px wide, phone kept at 2x) so the repo stays small.
Fails loudly (exit 1) on any JavaScript error or a missing local file, so a broken prototype is never shot silently.
"""
import functools, http.server, socketserver, sys, threading
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "screenshots"
SCREENS = ["home", "planner", "players", "players/411", "fixtures", "rivals"]
SIZES = {"phone": (390, 844), "desktop": (1440, 900)}


def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
    threading.Thread(target=h.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{h.server_address[1]}/prototypes/ui-redesign/"


def save(png_bytes, path, size):
    import io
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if size == "desktop":
        im = im.resize((1440, round(im.height * 1440 / im.width)), Image.LANCZOS)
    im.save(path, "WEBP", quality=82, method=6)


def main():
    concepts = sys.argv[1:] or ["a-refined", "b-analytics", "c-interactive"]
    OUT.mkdir(exist_ok=True)
    base, bad = serve(), []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for c in concepts:
            for size, (w, h) in SIZES.items():
                for theme in ("dark", "light"):
                    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, reduced_motion="reduce")
                    pg = ctx.new_page()
                    pg.on("pageerror", lambda e, c=c: bad.append(f"{c}: {e}"))
                    pg.on("response", lambda r, c=c: r.status >= 400 and bad.append(f"{c}: {r.status} {r.url}"))
                    screens = SCREENS if theme == "dark" else ["home", "players"]
                    for s in screens:
                        pg.goto(f"{base}{c}/index.html?theme={theme}#{s}")
                        pg.wait_for_load_state("networkidle")
                        pg.wait_for_timeout(250)
                        name = s.replace("/411", "-detail")
                        save(pg.screenshot(), OUT / f"{c}--{name}--{size}--{theme}.webp", size)
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
