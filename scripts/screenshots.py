"""Take README screenshots of the local site.

    npm run dev            # in one terminal (serves site/ on :8000)
    python3 scripts/screenshots.py

Needs Python Playwright: pip install playwright && python3 -m playwright install chromium
and a site/data.json (see "Run locally" in the README).
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
URL = "http://localhost:8000/"
SHOTS = [  # (file, view, width, height, theme, action)
    ("dashboard-desktop-dark.png", "week", 1440, 1000, "dark", None),
    ("dashboard-desktop-light.png", "week", 1440, 1000, "light", None),
    ("pitch-phone.png", "planner", 390, 844, "dark", "pitch"),
    ("player-detail-phone.png", "week", 390, 844, "dark", "player"),
    ("players-desktop.png", "players", 1440, 900, "dark", None),
    ("fixtures-desktop.png", "fixtures", 1440, 900, "dark", None),
]

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, view, w, h, theme, action in SHOTS:
            ctx = await browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 500 else 1, service_workers="block")
            await ctx.add_init_script(f"try{{localStorage.setItem('fpl.theme','{theme}')}}catch(e){{}}")
            page = await ctx.new_page()
            await page.goto(URL + "#" + view)
            await page.wait_for_selector(f".view-{view}")
            await page.wait_for_timeout(1200)  # kit images
            if action == "pitch":
                await page.locator(".pitchwrap").first.scroll_into_view_if_needed()
            elif action == "player":
                await page.click(".dash-cap >> nth=0"); await page.wait_for_timeout(400)
            await page.screenshot(path=str(OUT / name))
            print("saved", name)
            await ctx.close()
        await browser.close()

asyncio.run(main())
