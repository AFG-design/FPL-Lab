"""One command that says whether the site works end to end, for the verify skill (.claude/skills/verify/SKILL.md).

    python3 scripts/verify.py                # fresh build for team 8122679, then every step below
    python3 scripts/verify.py --no-build     # reuse site/data.json (quick re-run after a site-only change)
    python3 scripts/verify.py --team 123456  # another team

Steps, in order (independent ones run side by side so the whole run stays under about 2 minutes):
  1. build     python3 build.py TEAM site/data.json  }  together
  2. npm test  lint, whole-app check, node tests     }
  3. validate  python3 validate.py site/data.json (errors fail; warnings are printed, as on the Health page)
  4. screens   scripts/layout_check.py: every view at 390px and 1280px, no JS errors, no error cards, no sideways
               scroll, no missing site files                                            }  together
  5. squad     the homepage (both its Current GW and Next GW views, at 390px and 1280px) shows 15 players on the
               pitch and bench, and sensible team value and bank (below)                }
Reuses the existing checks rather than copying them: only the squad step is new, and it uses layout_check's server.

"Sensible" in step 5, all tested against the same data the page uses:
  - Team value is a £m figure between 80.0 and 120.0 (FPL squads start at 100.0 and drift a few £m either way);
    on Current GW it also equals the sum of today's prices of the 15 in data.json, as its label says.
  - In the bank is a £m figure from 0.0 to 30.0; on Current GW it equals data.json's manager.bank. In a Free Hit
    week the page shows "Unavailable" by design (meta.fh_restored), which is accepted only when that flag is set.
  - Missing figure ("Unavailable" otherwise, or no money row at all) fails, never passes quietly.

Missing input fails loudly: no network for the build, no site/data.json with --no-build, or no Playwright, each fails
the step that needs it and the summary names it. Later steps that need a step that failed are marked "not run".

build.py writes to history/ as a side effect (the hourly Refresh commits those files; a local check must not). Files
under history/ that were clean before the run are put back afterwards and files the run created there are removed,
and the summary lists them. Files you had already changed there are left alone.

Exit code 0 when every step passes, 1 otherwise. Prints a PASS/FAIL summary with the failing step(s) last.
"""
import argparse, json, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
WIDTHS = {"phone": (390, 844), "desktop": (1280, 900)}
VALUE_RANGE, BANK_RANGE = (80.0, 120.0), (0.0, 30.0)


def run(name, cmd, timeout=300):
    """Run one step; returns (name, ok, seconds, tail of output)."""
    t = time.time()
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        out, ok = (r.stdout + r.stderr).strip(), r.returncode == 0
    except subprocess.TimeoutExpired:
        out, ok = f"timed out after {timeout}s", False
    except FileNotFoundError as e:
        out, ok = str(e), False
    return name, ok, time.time() - t, out


def git_lines(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return [x for x in r.stdout.splitlines() if x.strip()] if r.returncode == 0 else None


def history_state():
    """(changed tracked files, untracked files) under history/, or None outside a git checkout."""
    changed = git_lines("diff", "--name-only", "HEAD", "--", "history")
    new = git_lines("ls-files", "--others", "--exclude-standard", "--", "history")
    return None if changed is None or new is None else (set(changed), set(new))


def restore_history(before):
    if before is None:
        return "history/: not a git checkout, nothing put back"
    after = history_state()
    put_back = sorted(after[0] - before[0])
    created = sorted(after[1] - before[1])
    if put_back:
        subprocess.run(["git", "checkout", "--", *put_back], cwd=ROOT, check=True)
    for f in created:
        (ROOT / f).unlink()
    if not put_back and not created:
        return "history/: build left nothing to put back"
    return f"history/: put back {len(put_back)} file(s) the build changed, removed {len(created)} it created " \
           f"({', '.join(put_back + created)})"


def parse_money(s):
    m = re.fullmatch(r"£(-?\d+(?:\.\d)?)m", s.strip())
    return float(m.group(1)) if m else None


def squad_check():
    """Step 5. Returns (name, ok, seconds, report)."""
    t = time.time()
    try:
        from playwright.sync_api import sync_playwright
        from layout_check import serve
    except ImportError as e:
        return "squad", False, time.time() - t, f"can't start: {e} (pip install playwright)"
    path = ROOT / "site" / "data.json"
    if not path.exists():
        return "squad", False, time.time() - t, "site/data.json missing"
    D = json.loads(path.read_text())
    price = {p["id"]: p.get("price") for p in D.get("players", [])}
    ids = [s["id"] for s in D.get("squad", [])]
    want_value = round(sum(price[i] for i in ids), 1) if ids and all(price.get(i) is not None for i in ids) else None
    want_bank, fh = D.get("manager", {}).get("bank"), bool(D.get("meta", {}).get("fh_restored"))
    lines, fails = [], []
    httpd, url = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for size, (w, h) in WIDTHS.items():
                ctx = browser.new_context(viewport={"width": w, "height": h}, service_workers="block")
                for home in ("current", "next"):
                    page = ctx.new_page()
                    errs = []
                    page.on("pageerror", lambda e, errs=errs: errs.append(f"uncaught: {e}"))
                    page.add_init_script(f"localStorage.setItem('fpl.home', JSON.stringify({home!r}))")
                    page.goto(f"{url}#week")
                    where = f"{home} GW @ {w}px"
                    try:
                        page.wait_for_selector(".view-week .home-pitch", timeout=20000)
                    except Exception:
                        fails.append(f"{where}: homepage pitch never rendered (.view-week .home-pitch missing after 20 s)")
                        page.close()
                        continue
                    n = page.locator(".home-pitch .lu-pc").count()
                    money = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.home-pitch .mrow .mr')]
                        .map(m => [m.querySelector('dt').textContent.trim(), m.querySelector('.mr-v').textContent.trim()]))""")
                    msg = []
                    if n != 15:
                        msg.append(f"{n} players on pitch and bench, not 15")
                    tv_s, bank_s = money.get("Team value"), money.get("In the bank")
                    tv = parse_money(tv_s) if tv_s else None
                    bank = parse_money(bank_s) if bank_s else None
                    if tv is None:
                        msg.append(f"team value not a £m figure: {tv_s!r}")
                    elif not VALUE_RANGE[0] <= tv <= VALUE_RANGE[1]:
                        msg.append(f"team value £{tv}m outside £{VALUE_RANGE[0]}m-£{VALUE_RANGE[1]}m")
                    elif home == "current" and want_value is not None and abs(tv - want_value) > 0.05:
                        msg.append(f"team value £{tv}m but today's prices of the {len(ids)} in data.json add up to £{want_value}m")
                    if bank_s == "Unavailable" and fh and home == "current":
                        pass   # Free Hit week: FPL shows the restored bank, so the page shows Unavailable on purpose
                    elif bank is None:
                        msg.append(f"bank not a £m figure: {bank_s!r}")
                    elif not BANK_RANGE[0] <= bank <= BANK_RANGE[1]:
                        msg.append(f"bank £{bank}m outside £{BANK_RANGE[0]}m-£{BANK_RANGE[1]}m")
                    elif home == "current" and want_bank is not None and abs(bank - want_bank) > 0.05:
                        msg.append(f"bank £{bank}m but data.json says £{want_bank}m")
                    msg += errs
                    lines.append(f"{'ok' if not msg else 'FAIL':4} {where}: {n} players, team value {tv_s}, bank {bank_s}")
                    fails += [f"{where}: {m}" for m in msg]
                    page.close()
                ctx.close()
            browser.close()
    finally:
        httpd.shutdown()
    return "squad", not fails, time.time() - t, "\n".join(lines + [f"  - {f}" for f in fails])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="8122679")
    ap.add_argument("--no-build", action="store_true", help="reuse site/data.json instead of building")
    a = ap.parse_args()
    t0 = time.time()
    results, hist_note = [], None
    with ThreadPoolExecutor(2) as ex:
        before = None if a.no_build else history_state()
        jobs = [ex.submit(run, "npm test", ["npm", "test"])]
        if not a.no_build:
            jobs.append(ex.submit(run, "build", [sys.executable, "build.py", a.team, "site/data.json"], 400))
        results += [j.result() for j in jobs]
        if not a.no_build:
            hist_note = restore_history(before)
    built = a.no_build or next(r for r in results if r[0] == "build")[1]
    if built:
        results.append(run("validate", [sys.executable, "validate.py", "site/data.json"]))
        shots = tempfile.mkdtemp(prefix="verify-shots-")
        with ThreadPoolExecutor(2) as ex:
            jobs = [ex.submit(run, "screens", [sys.executable, "scripts/layout_check.py", "--out", shots]), ex.submit(squad_check)]
            results += [j.result() for j in jobs]
    else:
        results += [(s, None, 0, "not run: the build failed") for s in ("validate", "screens", "squad")]

    order = ["build", "npm test", "validate", "screens", "squad"]
    results.sort(key=lambda r: order.index(r[0]))
    failed = [r for r in results if r[1] is not True]
    for name, ok, secs, out in failed:
        print(f"\n===== {name}: {'FAIL' if ok is False else 'NOT RUN'} =====")
        print("\n".join(out.splitlines()[-40:]))
    print("\n===== verify summary =====")
    for name, ok, secs, out in results:
        print(f"{'PASS' if ok else 'FAIL' if ok is False else 'SKIP':4}  {name:9} {secs:5.0f}s  {last_line(name, out)}")
    if hist_note:
        print(hist_note)
    print(f"{'PASS' if not failed else 'FAIL'}: {len(results) - len(failed)}/{len(results)} steps passed in {time.time() - t0:.0f}s"
          + (f"; failing step: {', '.join(r[0] for r in failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


def last_line(name, out):
    """The one line from a step's output worth showing in the summary."""
    keep = {"build": "wrote site/data.json", "validate": "validate:", "npm test": "# fail", "screens": "All "}
    lines = out.splitlines()
    hit = [x for x in lines if keep.get(name) and keep[name] in x]
    s = (hit[-1] if hit else lines[-1] if lines else "").strip()
    return s[:110]


if __name__ == "__main__":
    main()
