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

predict_sell() (params["xmins_sell"], off by default = shadow in build.py): boosters in xmins_sell/, trained by
tools/train_xmins_sell.py on the same rows and inputs plus three late-selling inputs from selling.py (sell_share,
sell_spike, log_own). fplmodel uses it for the next gameweek only; later weeks keep the boosters above.
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


def features(ctx, as_of, team_gws, kick, upcoming, skip=None, feats=None, targets=None):
    """{pid: feature vector} for every player whose club has a fixture in the horizon.
    skip: {pid: set of gameweeks} to leave out of his history (weeks he was injured / banned), or None.
    feats: feature names (default: the shipped model's 21); targets: dict filled with {pid: target round}."""
    feats = feats or _load()[0]
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
        if "sell_share" in feats:   # selling-informed model: late selling before the target round's deadline
            import selling
            f["sell_share"], f["sell_spike"], f["log_own"] = selling.features(ctx["sell"], pid, target)
        if targets is not None:
            targets[pid] = target
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


# ---------------------------------------------------------------- selling-informed model (shadow; param xmins_sell)
_sell_boosters = None


def _load_sell():
    """Boosters in xmins_sell/ (plain XGBoost JSON, trained by tools/train_xmins_sell.py on 2022-23 + 2023-24 with
    the 21 inputs above plus sell_share, sell_spike and log_own from selling.py). Missing files raise."""
    global _sell_boosters
    if _sell_boosters is None:
        import xgboost as xgb
        meta = json.load(open(os.path.join(HERE, "xmins_sell", "meta.json")))
        bs = {}
        for n in NAMES:
            b = xgb.Booster()
            b.load_model(os.path.join(HERE, "xmins_sell", f"{n}.json"))
            bs[n] = b
        _sell_boosters = (meta["features"], bs)
    return _sell_boosters


def predict_sell(ctx, as_of, team_gws, kick, upcoming, skip=None):
    """As predict(), from the selling-informed model, for players whose club plays in GW as_of (the window the
    selling counts belong to); others are left out and keep the plain model. Needs ctx["sell"] (selling.py sell
    table); a ctx without one raises, so the switch can't silently run on no data. Players with no selling data
    for as_of still get a prediction, with NaN selling inputs (XGBoost's missing value, as in training).
    Returns ({pid: (p_start, p_cameo, minutes if start, minutes if cameo)}, number with NaN sell_share)."""
    import xgboost as xgb
    if ctx.get("sell") is None:
        raise ValueError("xmins_sell is on but ctx has no 'sell' table (selling.py); refusing to guess")
    feats, bs = _load_sell()
    tg = {}
    fv = features(ctx, as_of, team_gws, kick, upcoming, skip, feats=feats, targets=tg)
    pids = [p for p in fv if tg[p] == as_of]
    if not pids:
        return {}, 0
    M = np.array([fv[p] for p in pids], dtype=float)
    X = xgb.DMatrix(M, feature_names=feats, missing=np.nan)
    ps, ms, pc, mc = (bs[n].predict(X) for n in NAMES)
    n_nan = int(np.isnan(M[:, feats.index("sell_share")]).sum())
    return ({p: (float(ps[i]), float(pc[i]), float(min(90.0, ms[i])), float(max(1.0, min(90.0, mc[i]))))
             for i, p in enumerate(pids)}, n_nan)
