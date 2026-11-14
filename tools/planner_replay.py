#!/usr/bin/env python3
"""FL-114: replay the planner on past seasons with one of its settings changed (report only).

    python3 tools/planner_replay.py '{"BENCH_W": 0.2}' --modes balanced
    python3 tools/planner_replay.py '{}' --modes balanced,chase            # the settings as optimise.py has them
    python3 tools/planner_replay.py '{"MIN_PROFIT": 2}' --seeds 0,1,2       # three starting squads a season (paired)

Overrides optimise.py's module settings for this run only (BENCH_W, MIN_PROFIT, HIT_GAIN, CHASE_BUDGET, DECAY,
FT_VALUE), then runs strategy_replay.py's replay: every gameweek each team re-plans with the site's own strategy code,
makes that week's moves and scores real points. optimise.py itself is never changed here. A setting name optimise.py
doesn't have stops the run (no silent typo). Seasons default to 2025-26 and 2024-25 from GW5.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import optimise, strategy_replay as sr

ALLOWED = {"BENCH_W", "MIN_PROFIT", "HIT_GAIN", "CHASE_BUDGET", "DECAY", "FT_VALUE"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("settings")
    ap.add_argument("--modes", default="balanced")
    ap.add_argument("--seasons", default="2025-26,2024-25")
    ap.add_argument("--sim", type=int, default=600)
    ap.add_argument("--seeds", default="0", help="starting squads: 0 = the best squad; N = ban 4 random players of it first")
    ap.add_argument("--json")
    a = ap.parse_args()
    over = json.loads(a.settings)
    bad = set(over) - ALLOWED
    if bad:
        sys.exit(f"planner_replay: not a setting this tool changes: {sorted(bad)}")
    # solve() takes bench_w, decay and ft_value as keyword defaults, which Python fixes when the function is defined,
    # so setting the module value alone wouldn't reach it: set both
    KW = {"BENCH_W": "bench_w", "DECAY": "decay", "FT_VALUE": "ft_value"}
    for k, v in over.items():
        if not hasattr(optimise, k):
            sys.exit(f"planner_replay: optimise.py has no {k}")
        setattr(optimise, k, v)
        if k in KW:
            kd = dict(optimise.solve.__kwdefaults__ or {})
            if KW[k] not in kd:
                sys.exit(f"planner_replay: optimise.solve has no {KW[k]} keyword")
            kd[KW[k]] = v
            optimise.solve.__kwdefaults__ = kd
    res = {}
    for s in a.seasons.split(","):
        for seed in (int(x) for x in a.seeds.split(",")):
            out = sr.summary(sr.replay(s, 5, 38, a.sim, tuple(a.modes.split(",")), seed, "best"))
            res[f"{s}/{seed}"] = out
            for m, r in out.items():
                print(f"RESULT {json.dumps(over)} {s} seed {seed} {m}: real {r['real']:.0f} proj {r['proj']:.1f} vs field {r['vs_field']:+.1f} "
                      f"spread {r['spread']} hits {r['hits']} moves {r['moves']}", flush=True)
    if a.json:
        json.dump({"settings": over, "res": res}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
