"""Text size and contrast check: opens every screen in light and dark, at 390px and 1280px, and fails on text that is
too small or below WCAG AA contrast (FL-123).

    python3 scripts/contrast_check.py            # needs site/data.json and site/data-extra.json, like layout_check.py
    python3 scripts/contrast_check.py --all      # list every failing element, not just two per colour pair

It measures what the browser draws, not the stylesheet:
  - size: every visible element with its own text (HTML, or SVG chart text) must be at least MIN_PX after layout, so
    em sizes and the browser's "smaller" defaults count as rendered;
  - contrast: each text element's colour, with its alpha and every ancestor's opacity, is blended over the pixels that
    are really behind it: the page is screenshotted with all text made transparent and the background is sampled
    across the boxes of the element's own text (not its padding, rounded corners or borders). Gradients, pseudo-element layers, faded cards and pictures are all measured as drawn.
    It must reach 4.5:1, or 3:1 for large text (24px, or 18.66px bold), at the 10th-percentile sample, so a small dot
    or icon inside the box (a pill's status dot) doesn't decide it, but a stripe behind part of the text does.
Not checked: text scrolled or clipped out of sight by an overflow box (it can't be seen in that state), and, as WCAG
exempts them, disabled controls and hidden text (display:none, visibility, closed <details>,
1px screen-reader text). Animations are switched off (reduced motion) so nothing is caught mid-fade.
Missing input fails loudly: no site/data.json or site/data-extra.json exits 2, as layout_check.py does; a screen that
never renders exits 2 too.
"""
import argparse, base64, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_check import SITE, VARIANTS, serve, views  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MIN_PX = 11
WIDTHS = {"phone": (390, 844), "desktop": (1280, 900)}
THEMES = ("dark", "light")

COLLECT = r"""(minPx) => {
  const cv = document.createElement("canvas"); cv.width = cv.height = 1;
  const cx = cv.getContext("2d", { willReadFrequently: true });
  const rgba = s => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = "#000"; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const name = e => typeof e.className === "string" ? e.className : e.className?.baseVal || "";
  const label = e => { const p = e.parentElement, pc = p ? name(p).trim() : "";
    return (pc ? "." + pc.split(/\s+/)[0] + " > " : "") + e.tagName.toLowerCase() + (name(e).trim() ? "." + name(e).trim().split(/\s+/).join(".") : ""); };
  // a text box scrolled or clipped out of sight by an overflow box (the xP table scrolls sideways on a phone) can't
  // be seen in this state, so it isn't measured: at least half of it must be inside every clipping ancestor
  const shown = (el, b) => {
    let [l, t, r, btm] = [b.left, b.top, b.right, b.bottom];
    for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.overflowX === "visible" && cs.overflowY === "visible") continue;
      const c = e.getBoundingClientRect(), cl = c.left + e.clientLeft, ct = c.top + e.clientTop;   // inside its border
      l = Math.max(l, cl); t = Math.max(t, ct); r = Math.min(r, cl + e.clientWidth); btm = Math.min(btm, ct + e.clientHeight);
    }
    return r > l && btm > t && (r - l) * (btm - t) >= 0.5 * b.width * b.height ? { left: l, top: t, width: r - l, height: btm - t } : null;
  };
  const items = [];
  for (const el of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE"].includes(el.tagName)) continue;
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    if (el.closest("[disabled],[aria-disabled=true],[hidden],[inert]")) continue;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true })) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    const cs = getComputedStyle(el), svg = el instanceof SVGElement;
    let fg = rgba(svg && cs.fill && cs.fill !== "none" ? cs.fill : cs.color);
    let op = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
    const px = parseFloat(cs.fontSize);
    items.push({ sel: label(el), text: el.textContent.trim().replace(/\s+/g, " ").slice(0, 40), px,
      large: px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight) >= 700), small: px < minPx,
      fg: [fg[0], fg[1], fg[2], fg[3] * op],
      // the boxes of the element's own text, not its padding, rounded corners or borders
      boxes: [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).flatMap(n => {
        const rg = document.createRange(); rg.selectNodeContents(n);
        return [...rg.getClientRects()].map(b => b.width > 1 && b.height > 1 && shown(el, b)).filter(Boolean)
          .map(b => [b.left + scrollX, b.top + scrollY, b.width, b.height]);   // only the part in sight is sampled
      }) });
  }
  // make every glyph transparent (and nothing else), so the screenshot shows only what is behind the text
  const st = document.createElement("style");
  st.textContent = `*, *::before, *::after { color: transparent !important; -webkit-text-fill-color: transparent !important;
    text-shadow: none !important; text-decoration-color: transparent !important; caret-color: transparent !important; }
    svg text, svg tspan { fill: transparent !important; stroke: transparent !important; }`;
  document.head.append(st);
  return items;
}"""

# runs in a blank page: decode the screenshot on a canvas and measure each item against the pixels behind it
MEASURE = r"""async ([png, items]) => {
  const img = new Image(); img.src = "data:image/png;base64," + png; await img.decode();
  const cv = document.createElement("canvas"); cv.width = img.width; cv.height = img.height;
  const cx = cv.getContext("2d", { willReadFrequently: true }); cx.drawImage(img, 0, 0);
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = c => "#" + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, "0")).join("");
  return items.map(it => {
    const s = [];
    for (const [x, y, w, h] of it.boxes) {
      // the middle of the line box, where the glyphs are (the top and bottom are half-leading)
      // ...and in from the ends by up to 3px, so a neighbouring element's 1px border or a space beside a chip isn't read
      const ix = Math.min(3, w * 0.15);
      const x0 = Math.max(0, Math.ceil(x + ix)), y0 = Math.max(0, Math.ceil(y + h * 0.2));   // rounded inwards
      const x1 = Math.min(cv.width - 1, Math.floor(x + w - ix) - 1), y1 = Math.min(cv.height - 1, Math.floor(y + h * 0.8) - 1);
      if (x1 < x0 || y1 < y0) continue;
      const data = cx.getImageData(x0, y0, x1 - x0 + 1, y1 - y0 + 1).data, W = x1 - x0 + 1, H = y1 - y0 + 1;
      const nx = Math.min(16, Math.max(2, Math.ceil(W / 6))), ny = Math.min(4, Math.max(2, Math.ceil(H / 5)));
      for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) {
        const px = Math.round(i * (W - 1) / (nx - 1)), py = Math.round(j * (H - 1) / (ny - 1)), k = 4 * (py * W + px);
        const bg = [data[k], data[k + 1], data[k + 2]], a = it.fg[3];
        const shown = [0, 1, 2].map(c => it.fg[c] * a + bg[c] * (1 - a));
        s.push({ cr: ratio(shown, bg), fg: hex(shown), bg: hex(bg) });
      }
    }
    if (!s.length) return null;
    s.sort((p, q) => p.cr - q.cr);
    const at = s[Math.floor(s.length * 0.1)];
    return { cr: +at.cr.toFixed(2), fg: at.fg, bg: at.bg };
  });
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="list every failing element")
    a = ap.parse_args()
    missing = [f for f in ("data.json", "data-extra.json") if not (SITE / f).exists()]
    if missing:
        print(f"contrast_check: site/{', site/'.join(missing)} missing; build first (python3 build.py TEAM_ID site/data.json)")
        sys.exit(2)
    vs = views()
    httpd, url = serve()
    # (theme, kind) -> {colour pair or size: [(screen, selector, text, detail)]}
    found, checked = defaultdict(lambda: defaultdict(list)), 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        blank = browser.new_page()
        for theme in THEMES:
            for size, (w, h) in WIDTHS.items():
                ctx = browser.new_context(viewport={"width": w, "height": h}, service_workers="block", reduced_motion="reduce")
                for v, var in [(v, None) for v in vs] + [(x[0], x) for x in VARIANTS if x[0] in vs]:
                    page = ctx.new_page()
                    page.add_init_script(f"localStorage.setItem('fpl.theme', {theme!r})")
                    if var:
                        page.add_init_script(f"localStorage.setItem({var[2]!r}, JSON.stringify({var[3]!r}))")
                    name = v if not var else f"{v}-{var[1]}"
                    page.goto(f"{url}#{v}")
                    try:
                        page.wait_for_selector(f".view-{v}", timeout=20000)
                    except Exception:
                        print(f"contrast_check: {name} never rendered in {theme} at {w}px")
                        sys.exit(2)
                    page.wait_for_timeout(800)
                    # one tall viewport, measured and photographed as it is: a full-page screenshot re-lays the page
                    # out (fixed bars move), so the boxes measured before it wouldn't line up with its pixels
                    tall = min(16000, page.evaluate("document.documentElement.scrollHeight"))
                    page.set_viewport_size({"width": w, "height": max(h, tall)})
                    page.wait_for_timeout(300)
                    items = page.evaluate(COLLECT, MIN_PX)
                    page.wait_for_timeout(50)
                    png = base64.b64encode(page.screenshot()).decode()
                    page.close()
                    res = blank.evaluate(MEASURE, [png, items])
                    where = f"{name} @ {w}px"
                    for it, m in zip(items, res):
                        checked += 1
                        if it["small"]:
                            found[(theme, "size")][f"{it['px']:g}px"].append((where, it["sel"], it["text"], ""))
                        need = 3 if it["large"] else 4.5
                        if m and m["cr"] < need - 0.005:
                            key = f"{m['fg']} on {m['bg']} ({m['cr']}:1, needs {need}:1)"
                            found[(theme, "contrast")][key].append((where, it["sel"], it["text"], f"{it['px']:g}px"))
                ctx.close()
        browser.close()
    httpd.shutdown()
    total = 0
    for theme in THEMES:
        for kind, what in (("contrast", "colour pairs below AA"), ("size", f"text sizes under {MIN_PX}px")):
            groups = found.get((theme, kind), {})
            elements = {(s, t) for hits in groups.values() for _, s, t, _ in hits}
            total += len(groups)
            print(f"{theme:5} {kind:8} {len(groups):3} {what} ({len(elements)} distinct elements)")
            for key, hits in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                uniq = list(dict.fromkeys((s, t, d, wh) for wh, s, t, d in hits))
                print(f"      {key}: {len(uniq)} element(s), e.g. "
                      + "; ".join(f"{s} \"{t}\" {d} [{wh}]".replace("  ", " ") for s, t, d, wh in uniq[:None if a.all else 2]))
    print(f"\n{checked} text elements measured.")
    if total:
        print(f"{total} problem group(s).")
        sys.exit(1)
    print(f"All text is {MIN_PX}px or more and meets WCAG AA in both themes at {' and '.join(f'{w}px' for w, _ in WIDTHS.values())}.")


if __name__ == "__main__":
    main()
