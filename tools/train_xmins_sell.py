#!/usr/bin/env python3
"""Train and test the selling-informed xMins model (xmins_sell/), against the shipped one (xmins/).

  python3 tools/train_xmins_sell.py            # train on 2022-23 + 2023-24, test on 2024-25 and 2025-26, save B
  python3 tools/train_xmins_sell.py --no-save  # test only

Models:  S = shipped boosters (xmins/, 21 inputs);  A = retrained here on the same 21 inputs;
         B = A's inputs + sell_share, sell_spike, log_own (selling.py), saved to xmins_sell/ as plain XGBoost JSON.
Rows: every player-fixture in the archive (vaastav merged_gw.csv; a double gameweek gives two rows with the same
inputs) whose club plays that gameweek, inputs from xmins.features() with data before the gameweek only and his
club at that point (archive team_at, as bench.py does). Targets per fixture: started (starts > 0); minutes if
started; bench appearance on rows where he did not start (conditional: the shipped cameo model's mean on
2023-24 rows with a recent appearance is 0.39 against a conditional rate of 0.40 and an unconditional one of 0.17;
fplmodel's default "B" combine caps it at 1 - start chance); minutes if a bench appearance.
Fixed hyperparameters (same for A and B, all four targets): HP below, 320 rounds (as the shipped boosters), seed 0.
"""
import csv, json, math, os, random, sys
from collections import defaultdict
import numpy as np
import xgboost as xgb

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import archive, selling, xmins
from fplmodel import prepare

HP = {"eta": 0.05, "max_depth": 4, "min_child_weight": 5, "subsample": 0.8, "colsample_bytree": 0.8,
      "lambda": 1.0, "seed": 0, "nthread": 4, "tree_method": "hist"}
ROUNDS = 320
TRAIN, TEST = ("2022-23", "2023-24"), ("2024-25", "2025-26")
SELL = ["sell_share", "sell_spike", "log_own"]
LIKELY, SELL_HI = 0.6, 0.08     # segment: S start chance >= 60% and 8%+ of owners sold (net) before the deadline


def season_rows(season):
    boot_now = json.load(open(os.path.join(HERE, "raw", "bootstrap.json")))
    boot, fixtures, live, priors, team_at = archive.load_season(season, boot_now)
    ctx = prepare(boot, fixtures, live, priors, None)
    ctx["sell"] = selling.from_archive(season)
    tgt = defaultdict(list)   # (pid, gw) -> [(minutes, starts)] per fixture
    with open(os.path.join(HERE, "archive", season, "merged_gw.csv"), encoding="utf-8", errors="ignore") as f:
        for r in csv.DictReader(f):
            tgt[(int(r["element"]), int(r["GW"]))].append((int(float(r["minutes"])), int(float(r["starts"]))))
    feats = xmins._load()[0] + SELL
    kick, team_gws = {}, defaultdict(set)
    for tid, lst in ctx["team_fix"].items():
        for (g, opp, home, fx) in lst:
            team_gws[tid].add(g)
            if fx.get("kickoff_time"):
                d = __import__("datetime").date.fromisoformat(fx["kickoff_time"][:10])
                kick[(tid, g)] = min(d, kick.get((tid, g), d))
    X, Y, meta = [], [], []
    for k in range(1, 39):
        cx = dict(ctx)
        cx["elements"] = {pid: dict(e, team=team_at(pid, k) or e["team"]) for pid, e in ctx["elements"].items()}
        upcoming = defaultdict(lambda: defaultdict(list))
        for tid, lst in ctx["team_fix"].items():
            for (g, opp, home, fx) in lst:
                if g == k:
                    upcoming[tid][g].append((opp, home))
        tg = {}
        fv = xmins.features(cx, k, team_gws, kick, upcoming, feats=feats, targets=tg)
        for pid, v in fv.items():
            if tg[pid] != k or (pid, k) not in tgt:
                continue
            fx = tgt[(pid, k)]
            for m, s in fx:
                X.append(v); Y.append((1.0 if s > 0 else 0.0, m, 1.0 if (m > 0 and s == 0) else 0.0))
                meta.append((k, pid, len(fx)))
    return np.array(X, dtype=float), np.array(Y, dtype=float), meta, feats


def train(X, Y, cols, names):
    Xc = X[:, cols]
    out = {}
    st, mins, cam = Y[:, 0], Y[:, 1], Y[:, 2]
    spec = {"start_model": (np.ones(len(Y), bool), st, "binary:logistic"),
            "minutes_given_start_model": (st == 1, mins, "reg:squarederror"),
            "cameo_model": (st == 0, cam, "binary:logistic"),
            "minutes_given_cameo_model": (cam == 1, mins, "reg:squarederror")}
    for n, (mask, y, obj) in spec.items():
        d = xgb.DMatrix(Xc[mask], label=y[mask], feature_names=names, missing=np.nan)
        out[n] = xgb.train(dict(HP, objective=obj), d, ROUNDS)
    return out


def predict(bs, X, cols, names):
    d = xgb.DMatrix(X[:, cols], feature_names=names, missing=np.nan)
    ps, ms, pc, mc = (bs[n].predict(d) for n in xmins.NAMES)
    ms, mc = np.minimum(90, ms), np.clip(mc, 1, 90)
    xm = ps * ms + np.minimum(pc, 1 - ps) * mc      # combine "B", as fplmodel's default
    return ps, pc, xm


def metrics(ps, pc, xm, Y, mask):
    st, mins, cam = Y[mask, 0], Y[mask, 1], Y[mask, 2]
    ns = st == 0
    return {"n": int(mask.sum()), "brier_start": float(np.mean((ps[mask] - st) ** 2)),
            "brier_cameo": float(np.mean((pc[mask][ns] - cam[ns]) ** 2)) if ns.any() else float("nan"),
            "xmin_rmse": float(np.sqrt(np.mean((xm[mask] - mins) ** 2))), "xmin_mae": float(np.mean(np.abs(xm[mask] - mins))),
            "xmin_bias": float(np.mean(xm[mask] - mins))}


def paired_ci(a, b, Y, gw, mask, n=2000):
    """Paired bootstrap over gameweeks of (Brier start b - a) on rows in mask."""
    st = Y[:, 0]
    by = defaultdict(lambda: [0.0, 0])
    for i in np.where(mask)[0]:
        x = by[gw[i]]; x[0] += (b[i] - st[i]) ** 2 - (a[i] - st[i]) ** 2; x[1] += 1
    ks = sorted(by)
    rng = random.Random(1)
    ms = []
    for _ in range(n):
        s = [by[ks[rng.randrange(len(ks))]] for _ in ks]
        ms.append(sum(x[0] for x in s) / sum(x[1] for x in s))
    ms.sort()
    return sum(x[0] for x in by.values()) / sum(x[1] for x in by.values()), ms[int(.025 * n)], ms[int(.975 * n) - 1]


def main(save=True):
    data = {s: season_rows(s) for s in TRAIN + TEST}
    feats = data[TRAIN[0]][3]
    c21, c24 = list(range(21)), list(range(24))
    Xtr = np.vstack([data[s][0] for s in TRAIN]); Ytr = np.vstack([data[s][1] for s in TRAIN])
    print(f"train rows {len(Ytr)}: start rate {Ytr[:, 0].mean():.4f}, bench-appearance rate {Ytr[:, 2].mean():.4f} "
          f"(of non-starts {Ytr[Ytr[:, 0] == 0, 2].mean():.4f}, the cameo target); sell_share NaN {np.isnan(Xtr[:, 21]).mean():.3%}")
    _, S = xmins._load()
    A, B = train(Xtr, Ytr, c21, feats[:21]), train(Xtr, Ytr, c24, feats)
    pS = predict(S, Xtr, c21, feats[:21])
    print(f"shipped S on training rows: mean start {pS[0].mean():.4f}, mean cameo {pS[1].mean():.4f}")
    res = {}
    for s in TEST:
        X, Y, meta, _ = data[s]
        gw = [m[0] for m in meta]
        single = np.array([m[2] == 1 for m in meta])
        P = {"S": predict(S, X, c21, feats[:21]), "A": predict(A, X, c21, feats[:21]), "B": predict(B, X, c24, feats)}
        sh = X[:, 21]
        recent = X[:, feats.index("played_avg_3")] > 0
        seg = {"all (one-fixture weeks)": single,
               "played in his last 3 rows": single & recent,
               f"likely starters (S >= {LIKELY:.0%})": single & (P["S"][0] >= LIKELY),
               f"likely starters, {SELL_HI:.0%}+ sold": single & (P["S"][0] >= LIKELY) & (np.nan_to_num(sh, nan=-9) >= SELL_HI),
               "sell_share missing": single & np.isnan(sh)}
        res[s] = {}
        print(f"--- {s} (test) ---  rows {len(Y)}, sell_share NaN {np.isnan(sh).mean():.3%}")
        print(f"  {'segment':34} {'n':>6} | {'Brier start S / A / B':>24} | {'Brier cameo|no start':>24} | {'xMin RMSE S / A / B':>20} | {'xMin bias S/A/B':>18}")
        for name, m in seg.items():
            if not m.sum():
                continue
            r = {k: metrics(*P[k], Y, m) for k in P}
            res[s][name] = r
            print(f"  {name:34} {r['S']['n']:6d} | " + " / ".join(f"{r[k]['brier_start']:.4f}" for k in "SAB") + " | "
                  + " / ".join(f"{r[k]['brier_cameo']:.4f}" for k in "SAB") + " | "
                  + " / ".join(f"{r[k]['xmin_rmse']:.2f}" for k in "SAB") + " | "
                  + " / ".join(f"{r[k]['xmin_bias']:+.2f}" for k in "SAB"))
        for (x, y) in (("A", "B"), ("S", "B"), ("S", "A")):
            for name in ("all (one-fixture weeks)", "played in his last 3 rows", f"likely starters, {SELL_HI:.0%}+ sold"):
                d, lo, hi = paired_ci(P[x][0], P[y][0], Y, gw, seg[name])
                print(f"  Brier start {y} - {x}, {name}: {d:+.4f} [{lo:+.4f}, {hi:+.4f}] (bootstrap over GWs)")
    if save:
        out = os.path.join(HERE, "xmins_sell")
        os.makedirs(out, exist_ok=True)
        for n, b in B.items():
            b.save_model(os.path.join(out, f"{n}.json"))
        json.dump({"features": feats, "train_seasons": list(TRAIN), "rounds": ROUNDS, "params": HP,
                   "xgboost": xgb.__version__, "targets": "per fixture: started; minutes if started; bench appearance "
                   "(unconditional); minutes if bench appearance", "script": "tools/train_xmins_sell.py",
                   "test": res}, open(os.path.join(out, "meta.json"), "w"), indent=1)
        print("saved", out)


if __name__ == "__main__":
    main(save="--no-save" not in sys.argv)
