"""Tap targets and two ARIA patterns on a touch screen (FL-124): opens every screen at 390px as a phone (touch, coarse
pointer) and fails on a control smaller than MIN_PX, a control nested inside a <summary>, or aria-pressed on a tab.

    python3 scripts/tap_check.py          # needs site/data.json and site/data-extra.json, like layout_check.py
    python3 scripts/tap_check.py --all    # list every failing element, not just a sample per kind

What counts as a control: button, a[href], summary, select, input (not hidden), and anything with role button, tab,
link, checkbox, switch, radio or menuitem. Its tap area is its border box, or a larger box that answers taps at its
edges (an ::after that extends it, say): the check asks the browser which element is hit 1px inside each edge of the
MIN_PX square centred on the control, so a padded hit area (or the control's own <label>) counts even when the visible box is smaller.
Exempt, as WCAG 2.5.8 exempts them: a link or link-style button inside a sentence (an inline or inline-block control
whose parent has its own text), and disabled or hidden controls. Text scrolled out of sight is still a control: it is checked.
Ambiguous input: a control whose centre is covered by another element (a sticky header over a table row) is checked
by its own box only, and listed as such, not passed or failed on what covers it.
Missing input fails loudly: no site/data.json or site/data-extra.json exits 2, as layout_check.py does.
"""
import argparse, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_check import SITE, VARIANTS, serve, views  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MIN_PX = 40
CONTROLS = ('button, a[href], summary, select, input:not([type=hidden]), [role=button], [role=tab], [role=link], '
            '[role=checkbox], [role=switch], [role=radio], [role=menuitem]')

PROBE = r"""([sel, min]) => {
  const name = e => typeof e.className === "string" ? e.className.trim() : "";
  const label = e => { const p = e.parentElement, pc = p ? name(p) : "";
    return (pc ? "." + pc.split(/\s+/)[0] + " > " : "") + e.tagName.toLowerCase() + (name(e) ? "." + name(e).split(/\s+/).join(".") : ""); };
  const txt = e => (e.getAttribute("aria-label") || e.textContent || "").trim().replace(/\s+/g, " ").slice(0, 30);
  const out = { small: [], nested: [], pressedTab: [] };
  for (const e of document.querySelectorAll("summary button, summary a[href], summary select, summary input, summary [role=button]"))
    out.nested.push({ sel: label(e), text: txt(e) });
  for (const e of document.querySelectorAll('[role=tab][aria-pressed]')) out.pressedTab.push({ sel: label(e), text: txt(e) });
  for (const e of document.querySelectorAll(sel)) {
    if (e.closest("[disabled],[aria-disabled=true],[hidden],[inert]") || e.matches(":disabled")) continue;
    if (e.checkVisibility && !e.checkVisibility({ visibilityProperty: true, contentVisibilityAuto: true })) continue;
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const cs = getComputedStyle(e);
    // inline in a sentence: an inline control whose parent has its own text (WCAG 2.5.8 inline exception)
    const p = e.parentElement;
    if (cs.display.startsWith("inline") && p && [...p.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    let w = r.width, h = r.height;
    if (w < min - 0.5 || h < min - 0.5) {
      // a hit area bigger than the box (padding pseudo-element): probe the edges of a min x min square at the centre
      // scroll only as far as needed: centring a cell in a sideways-scrolling table can park it under the table's
      // sticky first column, which a person scrolling the table never does
      e.scrollIntoView({ block: "center", inline: "nearest" });
      const b = e.getBoundingClientRect(), cx = b.left + b.width / 2, cy = b.top + b.height / 2, half = min / 2 - 1;
      // its own <label> counts: tapping a label works the control (the compare checkboxes are wrapped in one)
      const own = [e, ...(e.labels || [])];
      const hits = (x, y) => { const t = document.elementFromPoint(x, y); return !!t && own.some(o => t === o || o.contains(t)); };
      const centre = document.elementFromPoint(cx, cy);
      if (centre && !own.some(o => centre === o || o.contains(centre))) { out.small.push({ sel: label(e), text: txt(e), w: Math.round(w), h: Math.round(h), covered: true }); continue; }
      const wOk = hits(cx - half, cy) && hits(cx + half, cy), hOk = hits(cx, cy - half) && hits(cx, cy + half);
      if (wOk) w = Math.max(w, min); if (hOk) h = Math.max(h, min);
    }
    if (w < min - 0.5 || h < min - 0.5) out.small.push({ sel: label(e), text: txt(e), w: Math.round(w), h: Math.round(h) });
  }
  return out;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    missing = [f for f in ("data.json", "data-extra.json") if not (SITE / f).exists()]
    if missing:
        print(f"tap_check: site/{', site/'.join(missing)} missing; build first (python3 build.py TEAM_ID site/data.json)")
        sys.exit(2)
    vs = views()
    httpd, url = serve()
    small, nested, pressed, covered = defaultdict(set), defaultdict(set), defaultdict(set), set()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True,
                                  service_workers="block", reduced_motion="reduce")
        for v, var in [(v, None) for v in vs] + [(x[0], x) for x in VARIANTS if x[0] in vs]:
            page = ctx.new_page()
            if var:
                page.add_init_script(f"localStorage.setItem({var[2]!r}, JSON.stringify({var[3]!r}))")
            name = v if not var else f"{v}-{var[1]}"
            page.goto(f"{url}#{v}")
            try:
                page.wait_for_selector(f".view-{v}", timeout=20000)
            except Exception:
                print(f"tap_check: {name} never rendered")
                sys.exit(2)
            page.wait_for_timeout(800)
            if not page.evaluate("matchMedia('(pointer: coarse)').matches"):
                print("tap_check: the phone emulation doesn't report a coarse pointer, so touch styles weren't tested")
                sys.exit(2)
            r = page.evaluate(PROBE, [CONTROLS, MIN_PX])
            for x in r["small"]:
                small[f"{x['sel']} ({x['w']}x{x['h']})"].add((x["text"], name))
                if x.get("covered"):
                    covered.add((x["sel"], x["text"], name))
            for x in r["nested"]:
                nested[x["sel"]].add((x["text"], name))
            for x in r["pressedTab"]:
                pressed[x["sel"]].add((x["text"], name))
            page.close()
        browser.close()
    httpd.shutdown()

    def show(title, groups):
        n = sum(len(v) for v in groups.values())
        print(f"{title}: {len(groups)} kind(s), {n} control(s)")
        for k, hits in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            ex = sorted(hits)[:None if a.all else 2]
            print(f"   {k}: {len(hits)}, e.g. " + "; ".join(f'"{t}" [{w}]' for t, w in ex))
        return n
    bad = show(f"Under {MIN_PX}x{MIN_PX}px on touch", small)
    bad += show("Controls inside a <summary>", nested)
    bad += show("aria-pressed on role=tab", pressed)
    if covered:
        print(f"({len(covered)} of these are covered at their centre by another element, so only their own box was "
              f"measured, e.g. {sorted(covered)[0]})")
    if bad:
        sys.exit(1)
    print(f"Every control is at least {MIN_PX}x{MIN_PX}px on touch, none sits inside a <summary>, and no tab carries aria-pressed.")


if __name__ == "__main__":
    main()
