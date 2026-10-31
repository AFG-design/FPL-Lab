"""Expected-minutes model (XGBoost), retrained by xmins_train.py on 2022-23 (GW16 on), 2023-24, 2024-25 and 2025-26.

Two sets of four boosters, plain XGBoost JSON:
  xmins/A/   the 21 minutes-history inputs below                        (every week of the horizon)
  xmins/B/   the same 21 + three late-selling inputs (SELL)              (NEXT gameweek only, when selling is on)
each with
  start_model                chance he starts
  minutes_given_start_model  minutes if he starts
  cameo_model                chance of a bench appearance if he doesn't start (combine: see `xmins_combine` in fplmodel)
  minutes_given_cameo_model  minutes from the bench
and meta.json (input names, training seasons, hyperparameters). The original user-supplied boosters (trained on
2022-23 and 2023-24 by someone else) are no longer used: A, retrained the same way on more seasons, is the fallback.

The 21 inputs are rebuilt from FPL live data before `as_of` only (reconstructions of the original package's
definitions, kept unchanged for the retrain):
  - one history row per gameweek his club played and he had a live row (doubles: minutes and starts divided by
    the club's fixtures that week; played = any minutes);
  - history_gws = rows so far this season; gap_prev_gw = target round - last row's round;
  - days_since_last_pl_fixture = his club's first kick-off in the target round - its first kick-off in the last
    round it played;
  - rolling means over the last 3/5/10 rows (fewer rows: mean of what there is).
Missing data: no history rows -> every history input is NaN (XGBoost's missing value, as in training); no kick-off
date -> days NaN. Nothing is silently filled with a number.

Late-selling inputs (B), one definition for training, backtests and the live build (sell_from_rounds):
  per player, one row per round he has in FPL's element-summary history (or the archive's merged_gw.csv, which is
  the same data): transfers in / out during the window BEFORE that round's deadline (checked: GW1 is always 0, and
  this season's total transfers_in = sum of history rounds + bootstrap transfers_in_event), and `selected` (owners
  after that window's transfers).
    own_before = `selected` in his previous row (owners before this window); first row of his season:
                 selected - (in - out)
    sell_share = max(0, out - in) / own_before, capped at 1         (own_before < 1: NaN)
    sell_spike = sell_share - median(sell_share of his previous <= 6 rows, NaN ignored)   (no previous rows: NaN)
    log_own    = log10(own_before / managers + 1e-4)                (managers: sum of `selected` that round / 15;
                                                                     live: bootstrap total_players, ~0.5% apart)
  The live next-gameweek row (sell_next) uses bootstrap transfers_in_event / transfers_out_event for the open
  window and selected_by_percent x total_players only for the first-row fallback. Partial window: the inputs are
  whatever has been transferred so far; nothing is rescaled. build.py only switches B on in the last hours before
  the deadline (SELL_WINDOW_H), when most of the window has happened; see build.py.

Requires `xgboost` (not in requirements.txt): only imported when params["xmins"] is on.
"""
import json, math, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ("start_model", "minutes_given_start_model", "cameo_model", "minutes_given_cameo_model")
SELL = ("sell_share", "sell_spike", "log_own")
HIST = ("round", "was_home", "history_gws", "gap_prev_gw", "days_since_last_pl_fixture", "position_GK", "position_DEF",
        "position_MID", "position_FWD", "last_minutes", "last_starts", "last_played", "minutes_avg_3", "starts_avg_3",
        "played_avg_3", "minutes_avg_5", "starts_avg_5", "played_avg_5", "minutes_avg_10", "starts_avg_10",
        "played_avg_10")   # the 21 inputs of A, in this order; B = HIST + SELL
_boosters = {}


def model_dir(which="A", root=None):
    """Folder of booster set `which` ("A" or "B") under `root` (default xmins/)."""
    return os.path.join(root or os.path.join(HERE, "xmins"), which)


def _load(path=None):
    """(input names, {name: booster}) for the booster set in `path` (default: A). Missing files raise."""
    d = path or model_dir("A")
    if d not in _boosters:
        import xgboost as xgb
        meta = json.load(open(os.path.join(d, "meta.json")))
        bs = {}
        for n in NAMES:
            b = xgb.Booster()
            b.load_model(os.path.join(d, f"{n}.json"))
            bs[n] = b
        _boosters[d] = (meta["features"], bs)
    return _boosters[d]


# ---------------------------------------------------------------- late-selling inputs
def sell_from_rounds(rows, managers=None):
    """rows: {pid: [(round, transfers_in, transfers_out, selected), ...]} one row per round (doubles: the first row),
    any order. managers: {round: number of managers}; None -> sum of `selected` that round / 15.
    Returns {pid: {round: [sell_share, sell_spike, log_own]}} (NaN where undefined, see the module docstring)."""
    if managers is None:
        tot = {}
        for rs in rows.values():
            for (g, tin, tout, sel) in rs:
                tot[g] = tot.get(g, 0) + sel
        managers = {g: v / 15 for g, v in tot.items()}
    out = {}
    for pid, rs in rows.items():
        hist, prev_sel, res = [], None, {}
        for (g, tin, tout, sel) in sorted(rs):
            own = prev_sel if prev_sel is not None else sel - (tin - tout)
            m = managers.get(g) or 0
            if own >= 1:
                s = min(1.0, max(0, tout - tin) / own)
                lo = math.log10(own / m + 1e-4) if m > 0 else float("nan")
            else:
                s = lo = float("nan")
            prev = [h for h in hist[-6:] if not math.isnan(h)]
            spike = s - float(np.median(prev)) if prev and not math.isnan(s) else float("nan")
            res[g] = [s, spike, lo]
            hist.append(s)
            prev_sel = sel
        out[pid] = res
    return out


def sell_next(rows, gw, window, managers):
    """The live builder: inputs for the open window before gameweek `gw`'s deadline.
    rows: cached history rows (rounds < gw are used); window: {pid: (transfers_in_event, transfers_out_event,
    owners now)}, owners now = selected_by_percent / 100 x total_players (only used when he has no earlier row);
    managers: total_players. Returns {pid: [sell_share, sell_spike, log_own]} for every pid in `window`.
    Same function as training (sell_from_rounds), with the open window as his newest row."""
    sub = {}
    for pid, (tin, tout, own_now) in window.items():
        sub[pid] = [r for r in rows.get(pid, ()) if r[0] < gw] + [(gw, tin, tout, own_now)]
    res = sell_from_rounds(sub, {gw: managers})
    return {pid: res[pid][gw] for pid in window}


def selftest(rows, gws=None):
    """Live builder vs training builder on finished rounds of the cache: for each round g, rebuild g's inputs with
    sell_next (rows before g + g's own transfers as the 'open window', managers as in training) and compare with
    sell_from_rounds on the whole history. Returns the number of mismatches (0 = identical)."""
    full = sell_from_rounds(rows)
    tot = {}
    for rs in rows.values():
        for (g, tin, tout, sel) in rs:
            tot[g] = tot.get(g, 0) + sel
    bad = 0
    for g in sorted(gws or tot):
        win = {}
        for pid, rs in rows.items():
            r = next((x for x in rs if x[0] == g), None)
            if r:
                win[pid] = (r[1], r[2], r[3])
        live = sell_next(rows, g, win, tot[g] / 15)
        for pid, v in live.items():
            a = np.nan_to_num(np.array(v, float), nan=-99.0)
            b = np.nan_to_num(np.array(full[pid][g], float), nan=-99.0)
            if not np.allclose(a, b, atol=1e-12):
                bad += 1
    return bad


# ---------------------------------------------------------------- inputs and predictions
def features(ctx, as_of, team_gws, kick, upcoming, skip=None, path=None, targets=None, feats=None):
    """{pid: feature vector} for every player whose club has a fixture in the horizon, for the booster set in
    `path` (default A). skip: {pid: set of gameweeks} to leave out of his history, or None. targets: optional dict,
    filled with each player's target round. feats: input names to build instead of the set's (xmins_train.py).
    Selling inputs (only if the set lists them) come from ctx["sell"][pid][gw], and only when his target round is
    as_of (the window that closes at this deadline); a later target (blank week) or no entry -> NaN, never 0."""
    if feats is None:
        feats = _load(path)[0]
    nfx = {}
    for tid, lst in ctx["team_fix"].items():
        for (g, *_r) in lst:
            nfx[(tid, g)] = nfx.get((tid, g), 0) + 1
    out = {}
    pos_cols = {1: "position_GK", 2: "position_DEF", 3: "position_MID", 4: "position_FWD"}
    sell = ctx.get("sell") or {}
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
        if target == as_of and SELL[0] in f:
            sv = sell.get(pid, {}).get(target)
            if sv is not None:
                for name, v in zip(SELL, sv):
                    f[name] = v
        out[pid] = [f[k] for k in feats]
        if targets is not None:
            targets[pid] = target
    return out


def predict(ctx, as_of, team_gws, kick, upcoming, skip=None, path=None, next_only=False):
    """{pid: (p_start, p_cameo, minutes if start, minutes if cameo)}, one batch for every player.
    path: booster set (default A). next_only: only players whose next fixture is in gameweek as_of (for B)."""
    import xgboost as xgb
    feats, bs = _load(path)
    tg = {}
    fv = features(ctx, as_of, team_gws, kick, upcoming, skip, path, tg)
    if next_only:
        fv = {p: v for p, v in fv.items() if tg.get(p) == as_of}
    if not fv:
        return {}
    pids = list(fv)
    X = xgb.DMatrix(np.array([fv[p] for p in pids], dtype=float), feature_names=feats, missing=np.nan)
    ps, ms, pc, mc = (bs[n].predict(X) for n in NAMES)
    return {p: (float(ps[i]), float(pc[i]), float(min(90.0, ms[i])), float(max(1.0, min(90.0, mc[i]))))
            for i, p in enumerate(pids)}
