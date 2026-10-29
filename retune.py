#!/usr/bin/env python3
"""Weekly retune: refit the projection model's scalar parameters against this season's results, and keep the
new values only if they beat the current ones out of sample and don't hurt any backtest segment.

Usage (repo root):  python3 retune.py [RAW] [--force] [--dry-run]
  RAW        folder with bootstrap.json, fixtures.json, live{g}.json (tools/fetch_raw.py; default raw/)
  --force    run even if this gameweek has already been tuned
  --dry-run  print the decision; write neither model_params.json nor history/retune_log.json

Steps (all scored like backtest.evaluate: GW-k projections from data before k only, on players who played in
one of the 3 GWs before k, with the deadline status log as the live build uses it):
  1. Search: coordinate descent over TUNABLE (fplmodel.py), minimising MAE + |bias| (see loss()). Each value may move at most
     STEP_CAP (15%) from this week's starting value, and never outside its hard bounds, so one odd gameweek
     can't drag the model far.
  2. Walk-forward check: for each of the last 3 finished GWs t, fit on GW3..t-1 and score on t. The refit must
     beat the current values on pooled held-out MAE by at least MIN_GAIN, with held-out correlation no lower.
  3. Final fit on GW3..T (T = last finished GW), from the current values, same caps.
  4. Segment gate: backtest.segments + compare, with and without the status log (as CLAUDE.md asks for model
     changes). Any flagged segment (n >= 30, MAE worse by > 0.05 or bias moved > 0.2) rejects the change.
Accepted: model_params.json is rewritten (fplmodel loads it at import, so the next Refresh build uses it).
Every run that does work appends an entry to history/retune_log.json, whatever the decision.

Missing, late or ambiguous data (each is a logged "skipped" with the reason; nothing is changed):
  - raw/ missing or incomplete (no live{g}.json for a finished GW)  -> skipped
  - the latest finished GW not yet data_checked by FPL (bonus/corrections may still change)  -> skipped
  - fewer than MIN_GWS finished GWs in the backtest range GW3..T  -> skipped (too little to fit 16 values)
  - priors.json, odds/odds.json or history/status.json missing or unreadable  -> skipped: the live build uses
    all three, so tuning without one would fit a different model from the one that runs
  - the status log has no entry for GW T (saved late)  -> skipped: the newest week's flags would be unknown.
    Earlier GWs missing from the log are listed in the entry and the run goes ahead (the model treats them
    as unflagged, exactly as the live build does).
  - Understat set-piece data missing: used anyway as None. It only matters when sp_match > 0 (it is 0 and not
    tuned), so the projections are identical either way.
Already done (through_gw == T in model_params.json, or a logged accepted/rejected run for T): exits with no work
and no log entry, so re-running the workflow is harmless.
"""
import argparse, datetime as dt, json, math, os, sys, time

import fplmodel
from fplmodel import prepare, project, understat_sp, TUNABLE, check_params
from backtest import _in_pool, segments, compare, corr

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = fplmodel.MODEL_PARAMS_PATH
LOG_PATH = os.path.join(HERE, "history", "retune_log.json")
STATUS_PATH = os.path.join(HERE, "history", "status.json")
FIRST_GW = 3          # backtests start at GW3 (two weeks of history needed), as in backtest.py
MIN_GWS = 6           # finished GWs needed in GW3..T before tuning at all
HOLDOUT = 3           # walk-forward: the last 3 finished GWs are each held out in turn
MIN_GAIN = 0.01       # held-out MAE must improve by at least this (points per player-GW)
CORR_TOL = 0.0        # held-out correlation may fall by at most this (0: no lower at all)
STEP_CAP = 0.15       # each value moves at most 15% of its current size per week
GRID = 6              # candidate values per parameter per pass (plus the current one)
PASSES = 2            # coordinate-descent sweeps
# Search time budget (seconds, whole run). The cost grows with the season (about 150 s at GW8 locally, roughly
# linear in the number of GWs), so late in the season the search may not finish every sweep. Past the budget
# fit() stops and returns the best values so far; the entry records it ("search_cut_short"). Acceptance is
# unaffected: the cut-short values still have to pass the held-out and segment checks.
BUDGET = float(os.environ.get("RETUNE_BUDGET_SECS", 900))
_T0 = time.time()
_CUT = []
ROUND = {"w_pos": 1, "w_last": 1}   # decimals kept; everything else 4


def _r(k, v):
    return round(v, ROUND.get(k, 4))


# ---------------------------------------------------------------- data, as the live build loads it
def load_inputs(raw):
    """(ctx with status log, ctx without, T, notes) or raises SkipRun with the reason."""
    try:
        boot = json.load(open(os.path.join(raw, "bootstrap.json")))
        fixtures = json.load(open(os.path.join(raw, "fixtures.json")))
    except Exception as ex:
        raise SkipRun(f"raw data missing ({ex}); run tools/fetch_raw.py first")
    fin = [e for e in boot["events"] if e["finished"]]
    if not fin:
        raise SkipRun("no finished gameweek yet")
    last = max(fin, key=lambda e: e["id"])
    T = last["id"]
    if not last.get("data_checked"):
        raise SkipRun(f"GW{T} finished but FPL hasn't marked it data_checked (points may still change)", T)
    if T - FIRST_GW + 1 < MIN_GWS:
        raise SkipRun(f"only {max(0, T - FIRST_GW + 1)} finished GWs in GW{FIRST_GW}-{T}; need {MIN_GWS}", T)
    try:
        live = {g: json.load(open(os.path.join(raw, f"live{g}.json"))) for g in range(1, T + 1)}
    except Exception as ex:
        raise SkipRun(f"raw live data incomplete ({ex})", T)
    try:
        priors = json.load(open(os.path.join(HERE, "priors.json")))
        market = json.load(open(os.path.join(HERE, "odds", "odds.json")))
        status_log = json.load(open(STATUS_PATH))
        if not isinstance(status_log.get("gws"), dict):
            raise ValueError("history/status.json has no 'gws' table")
    except Exception as ex:
        raise SkipRun(f"an input the live build uses is missing or unreadable: {ex}", T)
    if str(T) not in status_log["gws"]:
        raise SkipRun(f"status log has no entry for GW{T} (saved late?)", T)
    notes = []
    gaps = [g for g in range(FIRST_GW, T + 1) if str(g) not in status_log["gws"]]
    if gaps:
        notes.append(f"status log missing GW{', GW'.join(map(str, gaps))}: treated as unflagged, as live")
    try:   # only used when sp_match > 0 (not tuned, currently 0): None gives identical projections
        sp = understat_sp(boot, fixtures, json.load(open(os.path.join(HERE, "understat", "shots.json"))),
                          json.load(open(os.path.join(HERE, "understat", "fpl_players.json")))["players"])
    except Exception:
        sp = None
        notes.append("Understat set-piece data unavailable (unused while sp_match = 0)")
    ctx_sl = prepare(boot, fixtures, live, priors, market, sp, status_log)
    ctx_ns = prepare(boot, fixtures, live, priors, market, sp, None)
    return ctx_sl, ctx_ns, status_log, T, notes


class SkipRun(Exception):
    def __init__(self, reason, through_gw=None):
        super().__init__(reason)
        self.reason, self.through_gw = reason, through_gw


# ---------------------------------------------------------------- scoring (same rows as backtest.evaluate)
def rows(ctx, gws, params):
    out = []
    for k in gws:
        res = project(ctx, k, horizon=1, params=dict(params, use_flags=False))["players"]
        for pid, r in res.items():
            a = ctx["pts_gw"].get(pid, {}).get(k)
            if a is not None and _in_pool(ctx, pid, k):
                out.append((r["xp"].get(k, 0.0), a))
    return out


def score(rs):
    xs, ys = [x for x, _ in rs], [y for _, y in rs]
    n = len(rs)
    return {"n": n, "mae": sum(abs(x - y) for x, y in rs) / n, "corr": corr(xs, ys),
            "rmse": math.sqrt(sum((x - y) ** 2 for x, y in rs) / n),
            "bias": sum(x - y for x, y in rs) / n}


# Search objective. Plain MAE is minimised by the *median* of each player's points, and FPL points are
# right-skewed (many 1-2s, a few hauls), so a pure-MAE fit drags every projection down: on GW3-8 it cut MAE
# by 0.11 but moved bias by -0.5 in every segment (all rejected by the segment gate). xP is an expected value,
# so the search minimises MAE + BIAS_W * |bias| ("mae_bias", default) or squared error ("mse"). Acceptance is
# still judged on held-out MAE and corr, as designed.
OBJECTIVE = os.environ.get("RETUNE_OBJECTIVE", "mae_bias")
BIAS_W = 1.0


def loss(rs):
    n = len(rs)
    if OBJECTIVE == "mse":
        return sum((x - y) ** 2 for x, y in rs) / n
    if OBJECTIVE == "mae":
        return sum(abs(x - y) for x, y in rs) / n
    return sum(abs(x - y) for x, y in rs) / n + BIAS_W * abs(sum(x - y for x, y in rs) / n)


def mae(ctx, gws, params):   # the search objective (name kept short: see loss)
    return loss(rows(ctx, gws, params))


# ---------------------------------------------------------------- search
def allowed(k, start):
    """Interval a value may take this week: start ± STEP_CAP (of the value, or of a tenth of the bound range
    when the value is at or near 0, so a parameter switched off can still move), within its hard bounds."""
    lo, hi = TUNABLE[k]
    d = STEP_CAP * max(abs(start), 0.1 * (hi - lo))
    return max(lo, start - d), min(hi, start + d)


def fit(ctx, gws, start):
    """Coordinate descent from `start` (dict of TUNABLE values) minimising loss() on gws. Returns (values, loss)."""
    cur = dict(start)
    best = mae(ctx, gws, cur)
    for _ in range(PASSES):
        moved = False
        for k in TUNABLE:
            lo, hi = allowed(k, start[k])
            if time.time() - _T0 > BUDGET:
                _CUT.append(len(gws))
                return cur, best
            for i in range(GRID + 1):
                v = _r(k, lo + (hi - lo) * i / GRID)
                if v == cur[k] or not lo <= v <= hi:
                    continue
                m = mae(ctx, gws, dict(cur, **{k: v}))
                if m < best - 1e-5:
                    best, cur[k], moved = m, v, True
        if not moved:
            break
    return cur, best


# ---------------------------------------------------------------- log + params files
def read_log():
    try:
        return json.load(open(LOG_PATH))
    except FileNotFoundError:
        return {"runs": []}


def append_log(entry, dry):
    log = read_log()
    log["runs"].append(entry)
    if dry:
        print("dry run: log entry not saved")
        return
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    tmp = LOG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(log, f, indent=1)
    os.replace(tmp, LOG_PATH)


def seg_json(ctx, gws, params, flag_log, status_label):
    """The same shape backtest.py --json writes, for backtest.compare."""
    rs = score(rows(ctx, gws, params))
    return {"gws": list(gws), "status_log": status_label, "flag_log": "history/status.json",
            "headline": {k: rs[k] for k in ("n", "mae", "corr", "bias")},
            "segments": segments(ctx, gws, params, flag_log=flag_log)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("raw", nargs="?", default=os.path.join(HERE, "raw"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", help="also write the before/after segment JSON files here")
    args = ap.parse_args()
    t0 = time.time()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    current = {k: fplmodel.DEFAULTS[k] for k in TUNABLE}
    check_params(current, "current model settings")
    entry = {"date": now, "through_gw": None, "params_source": fplmodel.MODEL_PARAMS["source"]}

    try:
        ctx, ctx_ns, status_log, T, notes = load_inputs(args.raw)
    except SkipRun as s:
        entry.update(through_gw=s.through_gw, decision="skipped", reason=s.reason)
        print("skipped:", s.reason)
        append_log(entry, args.dry_run)
        return 0
    entry["through_gw"] = T
    if notes:
        entry["notes"] = notes
    done = fplmodel.MODEL_PARAMS.get("through_gw") == T or any(
        r.get("through_gw") == T and r.get("decision") in ("accepted", "rejected") for r in read_log()["runs"])
    if done and not args.force:
        print(f"GW{T} already tuned (see {os.path.relpath(LOG_PATH, HERE)}); nothing to do. --force to rerun.")
        return 0

    gws = range(FIRST_GW, T + 1)
    # 2. walk-forward: fit on GW3..t-1, score on t, pooled over the last HOLDOUT finished GWs
    held_cur, held_new, folds = [], [], []
    for t in range(T - HOLDOUT + 1, T + 1):
        cand, _ = fit(ctx, range(FIRST_GW, t), current)
        rc, rn = rows(ctx, [t], current), rows(ctx, [t], cand)
        held_cur += rc; held_new += rn
        folds.append({"gw": t, "fit": f"GW{FIRST_GW}-{t - 1}", "mae_current": score(rc)["mae"],
                      "mae_refit": score(rn)["mae"]})
        print(f"  held out GW{t} (fit GW{FIRST_GW}-{t - 1}): MAE current {folds[-1]['mae_current']:.4f}, "
              f"refit {folds[-1]['mae_refit']:.4f}   [{time.time() - t0:.0f}s]")
    hc, hn = score(held_cur), score(held_new)
    held = {"gws": [f["gw"] for f in folds], "n": hc["n"], "mae_current": hc["mae"], "mae_refit": hn["mae"],
            "corr_current": hc["corr"], "corr_refit": hn["corr"], "bias_current": hc["bias"], "bias_refit": hn["bias"],
            "rmse_current": hc["rmse"], "rmse_refit": hn["rmse"], "objective": OBJECTIVE, "folds": folds}
    entry["held_out"] = held
    print(f"held-out GW{held['gws'][0]}-{held['gws'][-1]} (n={hc['n']}): MAE {hc['mae']:.4f} -> {hn['mae']:.4f}, "
          f"corr {hc['corr']:.4f} -> {hn['corr']:.4f}, bias {hc['bias']:+.3f} -> {hn['bias']:+.3f}, "
          f"RMSE {hc['rmse']:.4f} -> {hn['rmse']:.4f}")

    # 3. final fit on everything (always computed, so a rejection still logs what was proposed)
    final, _ = fit(ctx, gws, current)
    check_params(final, "retune result")
    entry["old"] = current
    entry["new"] = {k: v for k, v in final.items() if v != current[k]}
    a, b = score(rows(ctx, gws, current)), score(rows(ctx, gws, final))
    entry["headline"] = {"gws": f"GW{FIRST_GW}-{T}", "n": a["n"], "mae": [a["mae"], b["mae"]],
                         "corr": [a["corr"], b["corr"]], "bias": [a["bias"], b["bias"]]}
    print(f"in-sample GW{FIRST_GW}-{T}: MAE {a['mae']:.4f} -> {b['mae']:.4f}, corr {a['corr']:.4f} -> {b['corr']:.4f}")

    reasons = []
    if hc["mae"] - hn["mae"] < MIN_GAIN:
        reasons.append(f"held-out MAE gain {hc['mae'] - hn['mae']:+.4f} is under {MIN_GAIN}")
    if hn["corr"] < hc["corr"] - CORR_TOL:
        reasons.append(f"held-out corr fell {hc['corr']:.4f} -> {hn['corr']:.4f}")
    if not entry["new"]:
        reasons.append("the final fit kept every current value")

    # 4. segment gate, with and without the status log (flag split labelled from the log in both)
    flagged = []
    if entry["new"]:
        for label, c, sl in (("status log", ctx, "history/status.json"), ("no status log", ctx_ns, None)):
            A, B = seg_json(c, gws, current, status_log, sl), seg_json(c, gws, final, status_log, sl)
            if args.out_dir:
                os.makedirs(args.out_dir, exist_ok=True)
                tag = "_sl" if sl else ""
                for name, d in (("before", A), ("after", B)):
                    json.dump(d, open(os.path.join(args.out_dir, f"retune_{name}{tag}.json"), "w"), indent=1)
            print(f"segment check ({label}):")
            flagged += [f"{label}: {f}" for f in compare(A, B)]
        if flagged:
            reasons.append(f"{len(flagged)} segment(s) past the backtest limits")
    entry["flagged_segments"] = flagged
    if _CUT:
        entry["search_cut_short"] = f"time budget {BUDGET:.0f}s reached in {len(_CUT)} fit(s); best values so far used"
    entry["decision"] = "rejected" if reasons else "accepted"
    entry["reason"] = "; ".join(reasons) if reasons else (
        f"held-out MAE {hc['mae']:.3f} -> {hn['mae']:.3f}, corr {hc['corr']:.3f} -> {hn['corr']:.3f}; no segment flagged")
    entry["secs"] = round(time.time() - t0, 1)
    print(f"{entry['decision']}: {entry['reason']}  ({entry['secs']}s)")

    if entry["decision"] == "accepted" and not args.dry_run:
        out = {"_note": "Written by retune.py (weekly). Overrides fplmodel.DEFAULTS; delete the file to go back to "
                        "the hand-set defaults. Values must stay within fplmodel.TUNABLE bounds or the build fails.",
               "tuned_at": now, "through_gw": T, "fit_gws": [FIRST_GW, T], "params": final,
               "previous": current, "held_out": {k: held[k] for k in ("gws", "n", "mae_current", "mae_refit",
                                                                   "corr_current", "corr_refit", "bias_current",
                                                                   "bias_refit", "objective")}}
        tmp = PARAMS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(out, f, indent=1)
        fplmodel.load_model_params(tmp)   # re-read through the build's own loader: raises if anything is off
        os.replace(tmp, PARAMS_PATH)
        print(f"wrote {os.path.relpath(PARAMS_PATH, HERE)}")
    append_log(entry, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
