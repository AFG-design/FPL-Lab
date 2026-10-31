#!/usr/bin/env python3
"""Train the expected-minutes boosters (xmins.py) from the public vaastav/Fantasy-Premier-League archive.

  python3 xmins_train.py            # live boosters: xmins/A and xmins/B, trained on every season in SEASONS
  python3 xmins_train.py --folds    # bench/backtest fold models: archive/xmins_folds/<season>/{A,B}, each trained on
                                    # every season EXCEPT <season>, so bench.py tests that season out of sample
  python3 xmins_train.py --check    # also print the training rows and start rates per season

Needs xgboost (pip install xgboost-cpu==3.4.1) and network access the first time (archive.py caches the CSVs in
archive/, not committed). Deterministic: fixed hyperparameters (HP, ROUNDS), seed 0, no tuning on any test season;
retraining on the same data and xgboost version gives the same boosters.

Training rows: one per (season, gameweek k, player) where his club (as known before the deadline: archive.team_at)
has exactly ONE fixture in k and he has a row in k. Inputs: xmins.features() (the code the live model runs), with
the selling inputs from xmins.sell_from_rounds() on archive.load_transfers() (the same definition the live build
and the backtests use). Targets: started (starts > 0); minutes (capped at 90) if started; came off the bench if
not started; bench minutes if so.

Data gap: the archive has starts = 0 for every row of 2022-23 GW1-15 (FPL added the field mid-season). Those weeks
are kept for the HISTORY inputs of later weeks with starts imputed as minutes >= 45 (right 96.5% of the time on
2023-24) and are never used as targets.
"""
import datetime as dt, json, os, sys
from collections import defaultdict

import numpy as np

import archive, xmins

HERE = os.path.dirname(os.path.abspath(__file__))
SEASONS = ("2022-23", "2023-24", "2024-25", "2025-26")
FOLD_SEASONS = ("2024-25", "2025-26")      # archive seasons bench.py tests
HP = dict(max_depth=4, eta=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=10, seed=0, nthread=4)
ROUNDS = 500
IMPUTED_STARTS = {"2022-23": 15}           # season -> last GW whose starts are missing in the archive


def season_rows(season):
    """Training rows for one season: list of dicts (x_hist, x_sell, started, minutes, gw)."""
    boot_now = json.load(open(os.path.join(HERE, "raw", "bootstrap.json")))   # only for archive's scoring rules
    boot, fixtures, live, _priors, team_at = archive.load_season(season, boot_now)
    pstats = defaultdict(dict)
    last_imp = IMPUTED_STARTS.get(season, 0)
    for g, data in live.items():
        for x in data["elements"]:
            st = x["stats"]
            if g <= last_imp:
                st = dict(st, starts=1 if st["minutes"] >= 45 else 0, _imputed=True)
            pstats[x["id"]][g] = st
    team_fix = defaultdict(list)
    for f in fixtures:
        team_fix[f["team_h"]].append((f["event"], f["team_a"], True, f))
        team_fix[f["team_a"]].append((f["event"], f["team_h"], False, f))
    kick, team_gws, nfx = {}, defaultdict(set), defaultdict(int)
    for tid, lst in team_fix.items():
        for (g, opp, home, f) in lst:
            team_gws[tid].add(g)
            nfx[(tid, g)] += 1
            if f.get("kickoff_time"):
                d = dt.date.fromisoformat(f["kickoff_time"][:10])
                kick[(tid, g)] = min(d, kick.get((tid, g), d))
    elements = {e["id"]: e for e in boot["elements"]}
    ctx = {"elements": elements, "pstats": pstats, "team_fix": team_fix,
           "sell": xmins.sell_from_rounds(archive.load_transfers(season))}
    feats = list(xmins.HIST) + list(xmins.SELL)
    out = []
    for k in range(1, 39):
        cx = dict(ctx, elements={pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in elements.items()})
        upcoming = defaultdict(lambda: defaultdict(list))
        for tid, lst in team_fix.items():
            for (g, opp, home, f) in lst:
                if g == k:
                    upcoming[tid][g].append((opp, home))
        for pid, vec in xmins.features(cx, k, team_gws, kick, upcoming, feats=feats).items():
            s = pstats.get(pid, {}).get(k)
            if s is None or s.get("_imputed") or nfx.get((cx["elements"][pid]["team"], k)) != 1:
                continue
            out.append({"gw": k, "x": vec, "started": 1.0 if s["starts"] > 0 else 0.0,
                        "minutes": float(min(90, s["minutes"]))})
    return out


def train(rows, with_sell, out_dir, seasons):
    import xgboost as xgb
    names = list(xmins.HIST) + (list(xmins.SELL) if with_sell else [])
    X = np.array([r["x"][:len(names)] for r in rows], dtype=float)
    st = np.array([r["started"] for r in rows])
    mn = np.array([r["minutes"] for r in rows])
    cam = (st == 0) & (mn > 0)

    def fit(mask, y, obj):
        d = xgb.DMatrix(X[mask], label=y[mask], feature_names=names, missing=np.nan)
        return xgb.train(dict(HP, objective=obj), d, ROUNDS)

    allr = np.ones(len(rows), bool)
    models = {"start_model": fit(allr, st, "binary:logistic"),
              "minutes_given_start_model": fit(st == 1, mn, "reg:squarederror"),
              "cameo_model": fit(st == 0, cam.astype(float), "binary:logistic"),   # conditional on not starting
              "minutes_given_cameo_model": fit(cam, mn, "reg:squarederror")}
    os.makedirs(out_dir, exist_ok=True)
    for n, b in models.items():
        b.save_model(os.path.join(out_dir, f"{n}.json"))
    json.dump({"features": names, "train_seasons": list(seasons), "rows": len(rows),
               "hyperparameters": HP, "rounds": ROUNDS, "xgboost": xgb.__version__,
               "built_by": "xmins_train.py"}, open(os.path.join(out_dir, "meta.json"), "w"), indent=1)


def main(args):
    data = {s: season_rows(s) for s in SEASONS}
    if "--check" in args:
        for s, rs in data.items():
            print(s, len(rs), "rows, start rate", round(float(np.mean([r["started"] for r in rs])), 3))
    if "--folds" in args:
        for test in FOLD_SEASONS:
            tr = [s for s in SEASONS if s != test]
            rows = [r for s in tr for r in data[s]]
            for v, ws in (("A", False), ("B", True)):
                train(rows, ws, os.path.join(HERE, "archive", "xmins_folds", test, v), tr)
            print(f"fold models for {test}: trained on {tr}, {len(rows)} rows -> archive/xmins_folds/{test}/")
    else:
        rows = [r for s in SEASONS for r in data[s]]
        for v, ws in (("A", False), ("B", True)):
            train(rows, ws, xmins.model_dir(v), SEASONS)
        print(f"live boosters: trained on {list(SEASONS)}, {len(rows)} rows -> xmins/A, xmins/B")


if __name__ == "__main__":
    main(sys.argv[1:])
