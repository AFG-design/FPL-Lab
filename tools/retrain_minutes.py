#!/usr/bin/env python3
"""FL-162 walk-forward experiment; never writes the live xmins/ or history/ files.

python tools/retrain_minutes.py train --out /tmp/fl162
python tools/retrain_minutes.py evaluate --out /tmp/fl162
python tools/retrain_minutes.py backtest --out /tmp/fl162

Protocol: docs/experiments/fl-162-minutes-protocol.md. Plain JSON boosters, fixed
21 features / recipe, two variants. Calibration is fitted to the preceding
season's out-of-sample predictions, never the evaluation season. Missing inputs
or empty conditional training targets fail loudly. xmins_sell is not involved.
"""
import argparse
from collections import defaultdict
from contextlib import contextmanager, redirect_stdout
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import runpy
import sys

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import archive
import backtest
import bench
import xmins
from fplmodel import prepare, project
from tools.train_xmins_sell import HP, ROUNDS, train as fit_boosters

SEASONS = ('2022-23', '2023-24', '2024-25', '2025-26')
FOLDS = {'2024-25': SEASONS[:2], '2025-26': SEASONS[:3], 'current': SEASONS}
MODES = ('shipped', 'retrained', 'recalibrated')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2))


def season_rows(season, names):
    """Per-fixture targets; features see only earlier GWs and the club then.
    Doubles repeat the deadline feature vector, as in the existing trainer.
    """
    boot, fixtures, live, priors, team_at = archive.load_season(season, read(ROOT / 'raw/bootstrap.json'))
    ctx = prepare(boot, fixtures, live, priors)
    target = defaultdict(list)
    with (ROOT / 'archive' / season / 'merged_gw.csv').open() as f:
        for row in csv.DictReader(f):
            pid, gw = int(row['element']), int(row['GW'])
            if pid not in ctx['elements']:
                continue
            # Missing labels are not zero-minute non-starts.
            minutes, starts = float(row['minutes']), float(row['starts'])
            target[pid, gw].append((float(starts > 0), minutes, float(minutes > 0 and starts == 0)))
    kick, team_gws = {}, defaultdict(set)
    for tid, fixtures_ in ctx['team_fix'].items():
        for g, _, _, fx in fixtures_:
            team_gws[tid].add(g)
            if fx.get('kickoff_time'):
                day = dt.date.fromisoformat(fx['kickoff_time'][:10])
                kick[tid, g] = min(day, kick.get((tid, g), day))
    X, Y, meta = [], [], []
    for k in range(1, 39):
        cx = dict(ctx)
        cx['elements'] = {pid: dict(e, team=team_at(pid, k) or e['team']) for pid, e in ctx['elements'].items()}
        moved = {pid: {g: team_at(pid, g + 1) for g in gs if g < k and team_at(pid, g + 1)
                       and team_at(pid, g + 1) != cx['elements'][pid]['team']}
                 for pid, gs in ctx['pstats'].items() if pid in cx['elements']}
        upcoming = defaultdict(lambda: defaultdict(list))
        for tid, fixtures_ in ctx['team_fix'].items():
            for g, opp, home, _ in fixtures_:
                if g == k:
                    upcoming[tid][g].append((opp, home))
        fv = xmins.features(cx, k, team_gws, kick, upcoming, feats=names, moved=moved)
        for pid, vector in fv.items():
            labels = target.get((pid, k), [])
            for label in labels:
                X.append(vector); Y.append(label); meta.append((k, pid, len(labels)))
    if not X:
        raise ValueError(f'No training rows: {season}')
    return np.asarray(X), np.asarray(Y), np.asarray(meta)


def fit_calibration(probability, started):
    """Fixed ridge-logistic calibration on prior-season OOS rows, not test rows.
    Positive slope preserves ranking. Small ridge avoids separation; no tuning.
    """
    p, y = np.asarray(probability), np.asarray(started)
    if len(p) == 0 or len(np.unique(y)) < 2:
        raise ValueError('Calibration needs both starts and non-starts')
    z = logit(np.clip(p, 1e-6, 1 - 1e-6))
    def loss(v):
        a, b = v
        t = a + b * z
        return np.mean(np.logaddexp(0, t) - y * t) + 1e-4 * (a*a + (b - 1)**2)
    fit = minimize(loss, [0., 1.], method='L-BFGS-B', bounds=[(-10, 10), (0.05, 5)])
    if not fit.success or not np.isfinite(fit.x).all():
        raise ValueError(f'Calibration failed: {fit.message}')
    return [float(v) for v in fit.x]


class CalibratedStart:
    def __init__(self, booster, coefficients):
        self.booster, self.coefficients = booster, coefficients

    def predict(self, data):
        p = self.booster.predict(data)
        a, b = self.coefficients
        return expit(a + b * logit(np.clip(p, 1e-6, 1 - 1e-6)))


@contextmanager
def installed(models):
    """Override this process only; restore even when evaluation raises."""
    previous = xmins._boosters
    xmins._boosters = models
    try:
        yield
    finally:
        xmins._boosters = previous


def load_candidate(out, season, calibrated=False):
    folder = out / FOLDS[season][-1]
    meta = read(folder / 'meta.json')
    if tuple(meta['train_seasons']) != FOLDS[season]:
        raise ValueError('Candidate training seasons do not match the evaluation fold')
    models = {}
    for name in xmins.NAMES:
        model = xgb.Booster(); model.load_model(folder / f'{name}.json'); model.set_param({'nthread': 4})
        models[name] = model
    if calibrated:
        if meta['calibration_season'] != FOLDS[season][-1]:
            raise ValueError('Calibration must use the preceding season')
        models['start_model'] = CalibratedStart(models['start_model'], meta['calibration'])
    return meta['features'], models


def train(out):
    names = read(ROOT / 'xmins/meta.json')['features']
    if len(names) != 21 or any('sell' in n for n in names):
        raise ValueError('This experiment requires the shipped 21 non-selling inputs')
    data = {}
    for season in SEASONS:
        print('Preparing', season, flush=True)
        data[season] = season_rows(season, names)
        print('Rows', season, len(data[season][1]), flush=True)
    previous = None
    for i, season in enumerate(SEASONS):
        train_seasons = SEASONS[:i + 1]
        X = np.vstack([data[s][0] for s in train_seasons]); Y = np.vstack([data[s][1] for s in train_seasons])
        if not all(np.any(mask) for mask in (Y[:, 0] == 1, Y[:, 0] == 0, Y[:, 2] == 1)):
            raise ValueError('Missing conditional training target')
        calibration = None
        if previous is not None:
            Xcal, Ycal, meta = data[season]
            single = meta[:, 2] == 1
            p = previous['start_model'].predict(xgb.DMatrix(Xcal[single], feature_names=names))
            calibration = fit_calibration(p, Ycal[single, 0])
        print('Training through', season, 'rows', len(Y), flush=True)
        models = fit_boosters(X, Y, list(range(21)), names)
        folder = out / season; folder.mkdir(parents=True, exist_ok=True)
        for name, model in models.items():
            model.save_model(folder / f'{name}.json')
        hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for s in train_seasons for p in sorted((ROOT / 'archive' / s).glob('*.csv'))}
        write(folder / 'meta.json', {'features': names, 'train_seasons': train_seasons, 'rounds': ROUNDS,
                                    'params': HP, 'xgboost': xgb.__version__, 'source_sha256': hashes,
                                    'calibration_season': season if calibration else None,
                                    'calibration_train_seasons': SEASONS[:i], 'calibration': calibration})
        previous = models
        print('Saved', folder, 'calibration', calibration, flush=True)


def reliability(rows):
    """Fixed [0,10), ... [90,100] probability bins with observed start rate."""
    result = []
    for i in range(10):
        selected = [r for r in rows if min(9, int(r[0] * 10)) == i]
        if selected:
            result.append({'bin': f'{i*10}-{(i+1)*10}%', 'n': len(selected),
                           'mean_probability': float(np.mean([r[0] for r in selected])),
                           'started': float(np.mean([r[1] for r in selected]))})
    return result


def minutes_report(season):
    if season == 'current':
        ctx, team_at = bench.current_ctx(), None
        gws = range(3, bench._CUR['cur'] + 1)
    else:
        ctx, team_at = bench._season(season); gws = range(4, 39)
    rows = defaultdict(list)
    for k in gws:
        cx = dict(ctx)
        if team_at:
            cx['elements'] = {pid: dict(e, team=team_at(pid, k) or e['team']) for pid, e in ctx['elements'].items()}
            cx['team_gw_xg'] = bench._xg_at(ctx, team_at, k)
        res = project(cx, k, 1, {'use_flags': False})['players']
        nfx = backtest._one_fixture(cx)
        for pid, r in res.items():
            actual = cx['pstats'].get(pid, {}).get(k)
            if actual is None or nfx.get((cx['elements'][pid]['team'], k)) != 1:
                continue
            row = (min(1., r['ps_next']), float(actual['starts'] > 0), min(1., r['p60_next']),
                   float(actual['minutes'] >= 60), r['xmin'], actual['minutes'])
            rows['all'].append(row)
            if backtest._in_pool(cx, pid, k): rows['pool'].append(row)
            if backtest.in_regular_pool(cx, pid, k): rows['regular'].append(row)
    report = {}
    for pool, values in rows.items():
        a = np.asarray(values)
        report[pool] = {'n': len(a), 'brier_start': float(np.mean((a[:,0]-a[:,1])**2)),
                        'brier_60': float(np.mean((a[:,2]-a[:,3])**2)),
                        'xmin_rmse': float(np.sqrt(np.mean((a[:,4]-a[:,5])**2))),
                        'xmin_mae': float(np.mean(np.abs(a[:,4]-a[:,5]))), 'reliability': reliability(values)}
    return report


def correlation_ci(base, candidate, n=2000):
    """Paired GW-cluster bootstrap, preserving each GW's aligned player rows."""
    from random import Random
    clusters = []
    for k in sorted(set(base) & set(candidate)):
        b = {r[0]: r for r in base[k]}; c = {r[0]: r for r in candidate[k]}
        ids = sorted(set(b) & set(c))
        # sufficient statistics for Pearson correlation, avoiding materialising draws
        def sums(pred):
            x = np.array([pred[p][2] for p in ids]); y = np.array([b[p][3] for p in ids])
            return np.array([len(x), x.sum(), y.sum(), (x*x).sum(), (y*y).sum(), (x*y).sum()])
        if ids: clusters.append((sums(b), sums(c)))
    def corr(t):
        count, sx, sy, sxx, syy, sxy = t
        den = (count*sxx-sx*sx)*(count*syy-sy*sy)
        return (count*sxy-sx*sy)/np.sqrt(den) if den > 0 else float('nan')
    if not clusters: raise ValueError('No paired correlation observations')
    values = np.asarray(clusters); rng = Random(1); ds = []
    for _ in range(n):
        t = values[[rng.randrange(len(values)) for _ in values]].sum(axis=0)
        ds.append(corr(t[1])-corr(t[0]))
    t = values.sum(axis=0); ds.sort()
    return [float(corr(t[1])-corr(t[0])), float(ds[int(.025*n)]), float(ds[int(.975*n)-1])]


def horizon_ci(base, candidate, n=2000):
    from random import Random
    d = [candidate[k] - base[k] for k in sorted(set(base) & set(candidate))]
    if not d:
        raise ValueError('No paired horizon origins')
    rng = Random(1)
    means = sorted(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for _ in range(n))
    return [sum(d) / len(d), means[int(.025*n)], means[int(.975*n)-1]]


def evaluate(out):
    shipped = xmins._load()
    results, reports, raw = {}, {}, {}
    for season in FOLDS:
        results[season] = {'_h5': {}, '_regular_h5': {}}; reports[season] = {}; raw[season] = {}
        for mode in MODES:
            print('\nEVALUATING', season, mode, flush=True)
            models = shipped if mode == 'shipped' else load_candidate(out, season, mode == 'recalibrated')
            with installed(models):
                r = bench.compare({mode: {}}, seasons=(season,))[season]
                reports[season][mode] = minutes_report(season)
                raw[season][mode] = bench.run_current({}) if season == 'current' else bench.run_archive({}, season)
            results[season][mode] = r[mode]
            results[season]['_h5'][mode] = r['_h5'][mode]
            results[season]['_regular_h5'][mode] = r['_regular_h5'][mode]
            print('MINUTES', json.dumps(reports[season][mode]), flush=True)
        for mode in MODES[1:]:
            results[season].setdefault('_ci', {})[mode] = bench.paired_ci(results[season]['shipped'], results[season][mode])
            print(season, mode, bench.fmt_ci(results[season]['_ci'][mode]), flush=True)
            results[season].setdefault('_corr_ci', {})[mode] = correlation_ci(raw[season]['shipped'], raw[season][mode])
            print('correlation CI', results[season]['_corr_ci'][mode], flush=True)
            results[season].setdefault('_h5_ci', {})[mode] = horizon_ci(results[season]['_h5']['shipped']['_per'],
                                                                       results[season]['_h5'][mode]['_per'])
            print('5-GW picks CI', results[season]['_h5_ci'][mode], flush=True)
        write(out / 'results.json', results); write(out / 'minutes.json', reports)
    bench.pooled(results, list(MODES))
    # Report-only pooled second-pool evidence, keeping the deciding pool separate.
    second = {s: {'_h5': results[s]['_regular_h5'], **{m: {'_scores': results[s][m]['_regular_scores']}
                                                      for m in MODES}} for s in FOLDS}
    print('\nSECOND POOL (report only)')
    bench.pooled(second, list(MODES))
    results['_second_pooled'] = second.get('_pooled')
    write(out / 'results.json', results)


def run_backtests(out):
    shipped = xmins._load()
    for mode in MODES:
        models = shipped if mode == 'shipped' else load_candidate(out, 'current', mode == 'recalibrated')
        for status in (False, True):
            name = mode + ('-status' if status else '')
            argv = [str(ROOT / 'backtest.py'), str(ROOT / 'raw'), '--quick', '--json', str(out / f'{name}.json')]
            if status: argv += ['--status-log']
            before = sys.argv
            try:
                sys.argv = argv
                with installed(models), (out / f'{name}.log').open('w') as f, redirect_stdout(f):
                    runpy.run_path(str(ROOT / 'backtest.py'), run_name='__main__')
            finally:
                sys.argv = before
        print('Backtested', mode, flush=True)
    for mode in MODES[1:]:
        for suffix in ('', '-status'):
            print('COMPARE', mode, suffix or 'no status', flush=True)
            backtest.compare(out / f'shipped{suffix}.json', out / f'{mode}{suffix}.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('train', 'evaluate', 'backtest'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); out = args.out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError('Use an experiment directory outside the repository; live model/history files must stay untouched')
    out.mkdir(parents=True, exist_ok=True)
    {'train': train, 'evaluate': evaluate, 'backtest': run_backtests}[args.action](out)


if __name__ == '__main__':
    main()
