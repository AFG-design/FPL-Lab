"""Experimental: an external pre-trained expected-minutes model (XGBoost, trained on 2022-23 and 2023-24).

Source: a user-supplied joblib file (original_xmins_model.joblib). It was opened with a whitelist unpickler (no code
from the file ran) and its four boosters exported to plain XGBoost JSON in xmins/, so nothing here loads a pickle.

  start_model                chance he starts
  minutes_given_start_model  minutes if he starts
  cameo_model                chance of a bench appearance (combine: see `combine` param in fplmodel)
  minutes_given_cameo_model  minutes from the bench

The 21 inputs are rebuilt from FPL live data before `as_of` only. The package that built them for training
(fpl_xmins) was not supplied, so these definitions are reconstructions:
  - one history row per gameweek his club played and he had a live row (doubles: minutes and starts divided by
    the club's fixtures that week; played = any minutes);
  - history_gws = rows so far this season; gap_prev_gw = target round - last row's round;
  - days_since_last_pl_fixture = his club's first kick-off in the target round - its first kick-off in the last
    round it played;
  - rolling means over the last 3/5/10 rows (fewer rows: mean of what there is).
Missing data: no history rows -> every history input is NaN (XGBoost's missing value, as in training); no kick-off
date -> days NaN. Nothing is silently filled with a number.

Requires `xgboost` (not in requirements.txt): only imported when params["xmins"] is on.
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ("start_model", "minutes_given_start_model", "cameo_model", "minutes_given_cameo_model")
_boosters = None


def _load():
    global _boosters
    if _boosters is None:
        import xgboost as xgb
        meta = json.load(open(os.path.join(HERE, "xmins", "meta.json")))
        bs = {}
        for n in NAMES:
            b = xgb.Booster()
            b.load_model(os.path.join(HERE, "xmins", f"{n}.json"))
            bs[n] = b
        _boosters = (meta["features"], bs)
    return _boosters


def features(ctx, as_of, team_gws, kick, upcoming, skip=None):
    """{pid: (feature vector, target round)} for every player whose club has a fixture in the horizon.
    skip: {pid: set of gameweeks} to leave out of his history (weeks he was injured / banned), or None."""
    feats, _ = _load()
    nfx = {}
    for tid, lst in ctx["team_fix"].items():
        for (g, *_r) in lst:
            nfx[(tid, g)] = nfx.get((tid, g), 0) + 1
    out = {}
    pos_cols = {1: "position_GK", 2: "position_DEF", 3: "position_MID", 4: "position_FWD"}
    for pid, e in ctx["elements"].items():
        tid = e["team"]
        target = next((g for g in sorted(upcoming[tid]) if g >= as_of and upcoming[tid][g]), None)
        if target is None:
            continue
        gs = ctx["pstats"].get(pid, {})
        sk = (skip or {}).get(pid, set())
        rows = []
        for g in sorted(team_gws.get(tid, ())):
            if g >= as_of or g not in gs or g in sk:
                continue
            s, n = gs[g], max(1, nfx.get((tid, g), 1))
            rows.append((g, s["minutes"] / n, min(1.0, s["starts"] / n), 1.0 if s["minutes"] > 0 else 0.0))
        f = dict.fromkeys(feats, np.nan)
        f["round"] = target
        f["was_home"] = 1.0 if upcoming[tid][target][0][1] else 0.0
        for et, col in pos_cols.items():
            f[col] = 1.0 if e["element_type"] == et else 0.0
        f["history_gws"] = len(rows)
        if rows:
            f["gap_prev_gw"] = target - rows[-1][0]
            f["last_minutes"], f["last_starts"], f["last_played"] = rows[-1][1:]
            for w in (3, 5, 10):
                r = rows[-w:]
                f[f"minutes_avg_{w}"] = sum(x[1] for x in r) / len(r)
                f[f"starts_avg_{w}"] = sum(x[2] for x in r) / len(r)
                f[f"played_avg_{w}"] = sum(x[3] for x in r) / len(r)
        prev = [g for g in team_gws.get(tid, ()) if g < as_of]
        if prev and kick.get((tid, target)) and kick.get((tid, max(prev))):
            f["days_since_last_pl_fixture"] = (kick[(tid, target)] - kick[(tid, max(prev))]).days
        out[pid] = [f[k] for k in feats]
    return out


def predict(ctx, as_of, team_gws, kick, upcoming, skip=None):
    """{pid: (p_start, p_cameo, minutes if start, minutes if cameo)}, one batch for every player."""
    import xgboost as xgb
    feats, bs = _load()
    fv = features(ctx, as_of, team_gws, kick, upcoming, skip)
    if not fv:
        return {}
    pids = list(fv)
    X = xgb.DMatrix(np.array([fv[p] for p in pids], dtype=float), feature_names=feats, missing=np.nan)
    ps, ms, pc, mc = (bs[n].predict(X) for n in NAMES)
    return {p: (float(ps[i]), float(pc[i]), float(min(90.0, ms[i])), float(max(1.0, min(90.0, mc[i]))))
            for i, p in enumerate(pids)}
