#!/usr/bin/env python3
"""Score the selling-informed xMins shadow (param xmins_sell) against the live model on real results.

  python3 tools/score_shadow.py            # every finished GW with a saved shadow
  python3 tools/score_shadow.py --raw raw  # read live{g}.json from a folder instead of the API

Input: history/proj_gw{g}.json "xmins_sell" block, saved by build.py before each deadline (the last build before the
deadline overwrites it, so it holds the numbers as they stood at the deadline). Each player row:
[live start chance, shadow start chance, live xMin, shadow xMin, live xP, shadow xP, sell_share or null].
Results: /event/{g}/live/ (one API call per GW, or raw/live{g}.json). Start chance and minutes are scored on
players with exactly one fixture that week (doubles sum the stats); xP on everyone in the block.
Missing data: a GW whose snapshot has no shadow block (before this was added, or the shadow failed) is skipped and
listed; a player in the block with no live row (left the club, not registered) is skipped and counted.
Decision rule to switch xmins_sell on: start-chance Brier and xP MAE lower for the shadow over the pooled weeks, with
the paired bootstrap CI over GWs of the Brier difference below 0.
"""
import json, math, os, random, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(HERE, "history")
LIKELY, SELL_HI = 0.6, 0.08


def live_rows(g, raw):
    path = os.path.join(raw, f"live{g}.json") if raw else None
    if path and os.path.exists(path):
        data = json.load(open(path))
    else:
        req = urllib.request.Request(f"https://fantasy.premierleague.com/api/event/{g}/live/",
                                     headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    return {x["id"]: x for x in data["elements"]}


def main(argv):
    raw = argv[argv.index("--raw") + 1] if "--raw" in argv else None
    boot_ev = None
    try:
        req = urllib.request.Request("https://fantasy.premierleague.com/api/bootstrap-static/",
                                     headers={"User-Agent": "Mozilla/5.0 fpl-lab"})
        with urllib.request.urlopen(req, timeout=30) as r:
            boot_ev = {e["id"]: e for e in json.load(r)["events"]}
    except Exception as ex:
        if not raw:
            raise
        boot_ev = {e["id"]: e for e in json.load(open(os.path.join(raw, "bootstrap.json")))["events"]}
    per, skipped, nolive = {}, [], 0
    for f in sorted(os.listdir(HIST)):
        if not (f.startswith("proj_gw") and f.endswith(".json")):
            continue
        g = int(f[7:-5])
        snap = json.load(open(os.path.join(HIST, f)))
        sh = snap.get("xmins_sell")
        if not (boot_ev.get(g) or {}).get("finished"):
            continue
        if not sh or "players" not in sh:
            skipped.append(g)
            continue
        lv = live_rows(g, raw)
        rows = []
        for pid, (psl, pss, xml, xms, xpl, xps, ss) in sh["players"].items():
            x = lv.get(int(pid))
            if x is None:
                nolive += 1
                continue
            s = x["stats"]
            rows.append({"one": len(x.get("explain") or []) == 1, "st": 1.0 if s["starts"] > 0 else 0.0,
                         "min": s["minutes"], "pts": s["total_points"], "psl": psl, "pss": pss, "xml": xml, "xms": xms,
                         "xpl": xpl, "xps": xps, "ss": ss})
        per[g] = rows
    if skipped:
        print("finished GWs without a saved shadow (skipped):", skipped)
    if nolive:
        print(f"{nolive} shadow rows had no live row (skipped)")
    if not per:
        print("no finished GW with a saved shadow yet")
        return 0

    def summary(rows, label):
        one = [r for r in rows if r["one"]]
        if not rows:
            return
        n, n1 = len(rows), len(one)
        b = lambda k: sum((r[k] - r["st"]) ** 2 for r in one) / n1 if n1 else float("nan")
        mae = lambda k, a: sum(abs(r[k] - r[a]) for r in (one if a == "min" else rows)) / (n1 if a == "min" else n)
        print(f"  {label:32} n={n:5d} (one-fixture {n1:5d}) | Brier start live {b('psl'):.4f} shadow {b('pss'):.4f}"
              f" | xMin MAE {mae('xml', 'min'):.2f} -> {mae('xms', 'min'):.2f} | xP MAE {mae('xpl', 'pts'):.3f} -> {mae('xps', 'pts'):.3f}")

    allr = [r for rs in per.values() for r in rs]
    print(f"Selling-informed xMins shadow vs live, GWs {sorted(per)}")
    summary(allr, "all")
    summary([r for r in allr if r["psl"] >= LIKELY], f"live start chance >= {LIKELY:.0%}")
    summary([r for r in allr if r["psl"] >= LIKELY and r["ss"] is not None and r["ss"] >= SELL_HI],
            f"  ... and {SELL_HI:.0%}+ of owners sold")
    summary([r for r in allr if r["ss"] is None], "no selling data")
    for g, rs in sorted(per.items()):
        summary(rs, f"GW{g}")
    # paired bootstrap over GWs: Brier start shadow - live (one-fixture rows)
    d = {g: [sum((r["pss"] - r["st"]) ** 2 - (r["psl"] - r["st"]) ** 2 for r in rs if r["one"]),
             sum(1 for r in rs if r["one"])] for g, rs in per.items()}
    d = {g: v for g, v in d.items() if v[1]}
    ks = sorted(d)
    rng = random.Random(1)
    ms = []
    for _ in range(2000):
        s = [d[ks[rng.randrange(len(ks))]] for _ in ks]
        ms.append(sum(x[0] for x in s) / sum(x[1] for x in s))
    ms.sort()
    mean = sum(v[0] for v in d.values()) / sum(v[1] for v in d.values())
    print(f"Brier start shadow - live: {mean:+.4f} [{ms[50]:+.4f}, {ms[1949]:+.4f}] (bootstrap over {len(ks)} GWs)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
