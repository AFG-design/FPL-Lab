#!/usr/bin/env python3
"""Check a freshly built data.json before it is published.

Usage: python3 validate.py [site/data.json]

Hard failures (exit 1, so the Refresh workflow stops before uploading and the last good site stays live):
  - a player FPL lists at 0% for next gameweek with more than 0.5 xP that week
  - an Understat id used for two FPL players, or an FPL id claimed by two Understat ids (incl. overrides)
  - next gameweek's xP breakdown (xp_detail) not adding up to xP within 0.05
  - NaN, infinite or negative xP
  - a probability outside 0-1 (p_start, psub, dc_rate, chance of 10+/6+/blank, chance of playing)
  - a real-starts record (st5) with more starts than games
  - expected minutes (xmin) outside 0-180, or NaN
  - the xMins minutes model switched on but any player with a next-GW fixture fell back to the old counts
  - a Review week whose pre-deadline snapshot (history/proj_gw{g}.json) exists but wasn't used
Warnings (printed, and saved in data.json "health" for the Health page; never fail the build):
  - a player with 300+ minutes and no Understat row (and no manual override)
  - no betting odds for any of next gameweek's fixtures
  - a gameweek in progress with no pre-deadline snapshot for the xP table's live column (meta.xp_cur), or a
    snapshot with fewer entries than half the players (it normally leaves out only players projected 0)
  - player odds (history/player_odds_gw*.json) for the latest finished-deadline gameweek missing a checkpoint
    (72, 24 or 3 h before the deadline), when that gameweek's file uses per-checkpoint snapshots. The model doesn't
    use player odds yet; this keeps the history complete for testing them. Skipped (not warned) when no file has
    snapshots, e.g. with no ODDS_API_KEY.
"""
import json, math, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        return None


def is_bad(x):
    return x is None or not isinstance(x, (int, float)) or math.isnan(x) or math.isinf(x)


def main(path):
    D = json.load(open(path))
    extra = (load(os.path.join(os.path.dirname(os.path.abspath(path)), "data-extra.json")) or {}).get("players", {})
    us = (load(os.path.join(HERE, "understat", "fpl_players.json")) or {}).get("players", {})
    ov = {int(k): int(v) for k, v in (load(os.path.join(HERE, "understat_overrides.json")) or {}).items() if not k.startswith("_")}
    g = D["meta"].get("next_gw")
    gk = str(g)
    errors, warnings = [], []
    name = lambda p: f'{p["name"]} ({p["id"]})'

    for p in D["players"]:
        xp = p.get("xp") or {}
        for gw, v in xp.items():
            if is_bad(v) or v < 0:
                errors.append(f"{name(p)}: xP GW{gw} = {v}")
        nxt = xp.get(gk, 0) or 0
        if p.get("chance") == 0 and not is_bad(nxt) and nxt > 0.5:
            errors.append(f"{name(p)}: {nxt:.2f} xP in GW{g} but FPL has him at 0% ({p.get('news') or p.get('status')})")
        probs = {"p_start": p.get("p_start"), "psub": p.get("psub"), "dc_rate": p.get("dc_rate")}
        if p.get("chance") is not None:
            probs["chance"] = p["chance"] / 100
        for gw, d in (p.get("dist") or {}).items():
            for i, lab in enumerate(("p10", "p6", "blank")):
                probs[f"dist GW{gw} {lab}"] = d[i]
        for k, v in probs.items():
            if v is not None and (is_bad(v) or not 0 <= v <= 1):
                errors.append(f"{name(p)}: {k} = {v} (not a probability)")
        det = (extra.get(str(p["id"])) or {}).get("xp_detail", p.get("xp_detail"))
        if det and xp.get(gk) is not None and abs(sum(det.values()) - xp[gk]) > 0.05:
            errors.append(f"{name(p)}: xp_detail adds up to {sum(det.values()):.2f}, xP GW{g} is {xp[gk]:.2f}")
        xm = p.get("xmin")
        if xm is not None and (is_bad(xm) or not 0 <= xm <= 180):
            errors.append(f"{name(p)}: xmin = {xm} (expected minutes must be 0-180)")
        st5 = p.get("st5")
        if st5 is not None and not (len(st5) == 2 and 0 <= st5[0] <= st5[1]):
            errors.append(f"{name(p)}: st5 = {st5} (starts must be between 0 and games)")
        mins = p.get("mins") or 0
        if mins >= 300 and str(p["id"]) not in us and p["id"] not in ov.values():
            warnings.append(f"{name(p)}: {mins} minutes but no Understat match (add to understat_overrides.json)")

    # minutes model: if xMins is on, every player with a next-GW fixture must have been projected by it
    mm = D["meta"].get("minutes_model")
    if mm and mm.get("xmins_on") and mm.get("counts"):
        errors.append(f"xMins minutes model is on but {mm['counts']} players with a GW{g} fixture fell back to the "
                      f"old counts ({mm.get('xmins', 0)} used xMins)")

    # Understat: one-to-one both ways
    dup_us = [u for u, n in Counter(v["us_id"] for v in us.values()).items() if n > 1]
    if dup_us:
        errors.append(f"Understat ids used for more than one FPL player: {dup_us}")
    dup_fpl = [f for f, n in Counter(ov.values()).items() if n > 1]
    by_us = {v["us_id"]: int(k) for k, v in us.items()}
    dup_fpl += [f for u, f in ov.items() if u in by_us and by_us[u] != f]
    dup_fpl += [int(k) for k, v in us.items() if int(k) in ov.values() and ov.get(v["us_id"]) != int(k)]
    if dup_fpl:
        errors.append(f"FPL ids with more than one Understat source (check understat_overrides.json): {sorted(set(dup_fpl))}")

    # Review: "projected before the deadline" must be the saved snapshot wherever one exists
    for w in (D.get("review") or {}).get("weeks", []):
        if os.path.exists(os.path.join(HERE, "history", f'proj_gw{w["gw"]}.json')) and w.get("xi_proj") is not None:
            if w.get("proj_src") != "snapshot" or (w.get("decision") and w["decision"].get("src") != "snapshot"):
                errors.append(f'Review GW{w["gw"]}: a pre-deadline snapshot exists but the review re-ran the model')

    # xP table live column: the gameweek in progress should have its pre-deadline projections
    xc = D["meta"].get("xp_cur")
    if xc and xc.get("status") != "snapshot":
        warnings.append(f'xP table GW{xc.get("gw")} live column has no projections ({xc.get("status")})')
    elif xc and xc.get("in_snapshot", 0) < 0.5 * len(D["players"]):
        warnings.append(f'xP table GW{xc["gw"]} live column: the snapshot has only {xc.get("in_snapshot", 0)} players '
                        f'for {len(D["players"])} listed; players not in it show 0')

    # odds for next gameweek
    odds = load(os.path.join(HERE, "odds", "odds.json")) or {}
    if g and not any(m.get("gw") == g and not m.get("played") for m in odds.get("matches", [])):
        warnings.append(f"No betting odds for any GW{g} fixture: fixture xG comes from team ratings only")

    # player odds history: the last gameweek whose deadline has passed should have all three checkpoints
    po = sorted(((int(f[len("player_odds_gw"):-5]), f) for f in os.listdir(os.path.join(HERE, "history"))
                 if f.startswith("player_odds_gw") and f.endswith(".json")), reverse=True)
    for pg, f in po:
        if pg >= g:   # the coming gameweek is still being collected
            continue
        snaps = (load(os.path.join(HERE, "history", f)) or {}).get("snapshots")
        if snaps is not None:
            missing = [h for h in ("72", "24", "3") if h not in snaps]
            if missing:
                warnings.append(f"Player odds GW{pg}: no {', '.join(m + ' h' for m in missing)} snapshot "
                                f"(check the ODDS_API_KEY secret and credits)")
        break
    # Planner strategy tabs (views/planner.js): each tab shows one optimiser plan per strategy. Every plan must name
    # players we list and field a legal XI; a strategy with no plans (build.py drops Play safe and Chase rank when the
    # field ownership file is missing) is a warning, and the tab says so instead of showing the Balanced plan.
    pids = {p["id"] for p in D["players"]}
    plans = D.get("plans") or {}
    if not plans:
        warnings.append("No optimiser plans: the Planner strategy tabs show a 'no plan' message")
    for k, pl in plans.items():
        for wk in pl.get("weeks", []):
            unknown = [i for i in wk.get("in", []) + wk.get("out", []) + wk.get("xi", []) if i not in pids]
            if unknown:
                errors.append(f"Plan {k} GW{wk.get('gw')}: players {unknown[:5]} are not in the player list")
            if len(wk.get("xi", [])) != 11 or wk.get("captain") not in wk.get("xi", []):
                errors.append(f"Plan {k} GW{wk.get('gw')}: XI has {len(wk.get('xi', []))} players or captain outside it")
            if len(wk.get("in", [])) != len(wk.get("out", [])):
                errors.append(f"Plan {k} GW{wk.get('gw')}: {len(wk.get('in', []))} in vs {len(wk.get('out', []))} out")
    if plans:
        for mode, label in (("safe", "Play safe"), ("chase", "Chase rank")):
            if not any(k.startswith(mode + "_") for k in plans):
                warnings.append(f"No {label} plans this build (field ownership missing?): its Planner tab shows a 'no plan' message")
    D["health"] = {"checked": D["meta"].get("built"), "ok": not errors, "errors": errors[:50], "warnings": warnings}
    with open(path, "w") as f:
        json.dump(D, f, separators=(",", ":"))
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"validate: {len(D['players'])} players, GW{g}: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join("site", "data.json")))
