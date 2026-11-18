"""Build prototypes/ui-redesign/shared/sample-data.js from a published FPL LAB data.json.

    python3 prototypes/ui-redesign/shared/extract.py PATH/TO/data.json

Prototype-only. Reads a data.json snapshot (public FPL API data as the live site publishes it) and writes a trimmed,
read-only sample for the three design prototypes. Rival managers are anonymised. Nothing here is used by site/ or build.py.
Missing input fails loudly (KeyError / FileNotFoundError); there are no silent defaults.
"""
import json, sys
from pathlib import Path

src = json.load(open(sys.argv[1]))
OUT = Path(__file__).with_name("sample-data.js")
meta, mgr = src["meta"], src["manager"]
gws = [str(g) for g in range(meta["next_gw"], meta["next_gw"] + 5)]
teams = {int(k): {"short": t["short"], "name": t["name"], "code": t["code"],
                  "fx": {g: [[f["opp"], f["home"], f["fdr"]] for f in t["fx"].get(g, [])] for g in gws}}
         for k, t in src["teams"].items()}
P = {p["id"]: p for p in src["players"]}
squad_ids = [s["id"] for s in src["squad"]]


def slim(p):
    return {"id": p["id"], "name": p["name"], "full": p["full"], "team": p["team"], "pos": p["pos"], "price": p["price"],
            "own": p["own"], "form": p["form"], "pts": p["pts"], "xg": p["xg"], "xa": p["xa"], "xgi90_4": p["xgi90_4"],
            "nailed": p["nailed"], "start": p["start_next"], "xmin": p["xmin"], "status": p["status"], "news": p["news"],
            "chance": p["chance"], "xp": {g: p["xp"].get(g) for g in gws}, "xp1": p["xp1"], "xp5": p["xp5"],
            "sp": [k for k, v in (p.get("sp") or {}).items() if v], "tin": p["tin"], "tout": p["tout"],
            "goals": p["goals"], "assists": p["assists"], "cs": p["cs"], "bonus": p["bonus"], "mins": p["mins"],
            "pts4": p["pts4"], "dist": p["dist"].get(gws[0])}


top = sorted((p for p in src["players"] if p.get("ok")), key=lambda p: -p["xp5"])[:80]
ids = {p["id"] for p in top} | set(squad_ids)
for name, pid in src["recommended"].items():
    for w in src["plans"][pid]["weeks"]:
        ids |= set(w["in"]) | set(w["out"])
plans = {}
for strat, pid in src["recommended"].items():
    pl = src["plans"][pid]
    plans[strat] = {"vs_none": pl["vs_none"], "xp_total": pl["xp_total"], "ft_left": pl["ft_left"],
                    "weeks": [{k: w[k] for k in ("gw", "in", "out", "xi", "bench", "captain", "vice", "ft", "hits", "bank", "xp", "spread")} for w in pl["weeks"]]}
lg = src["crowd"]["leagues"][0]
rows = []
for i, r in enumerate(lg["rows"][:12]):
    rows.append({"name": "You" if r["me"] else f"Rival {chr(65 + i)}", "team": mgr["team"] if r["me"] else f"Sample FC {i + 1}",
                 "me": r["me"], "rank": r["rank"], "last": r["last_rank"], "total": r["total"], "gw": r["gw_pts"],
                 "chip": r["chip"], "cap": next((pid for pid, m in r["picks"] if m >= 2), None)})
if not any(r["me"] for r in rows):
    rows.append({"name": "You", "team": mgr["team"], "me": True, "rank": lg["my_rank"], "last": lg["my_rank"], "total": mgr["points"],
                 "gw": mgr["gw_points"], "chip": None, "cap": src["lineup"]["captain"]})
out = {
    "_label": "SAMPLE DATA: FPL LAB snapshot of " + meta["built"] + " (public FPL API). Rival managers anonymised. Prototype only.",
    "meta": {k: meta[k] for k in ("built", "next_gw", "cur_gw", "deadline", "picks_gw")},
    "manager": {k: mgr[k] for k in ("team", "points", "rank", "gw_points", "bank", "value", "free_transfers", "total_players")},
    "history": src["history"], "gws": [int(g) for g in gws],
    "squad": src["squad"], "lineup": {k: src["lineup"][k] for k in ("xi", "bench", "captain", "vice", "xp_best", "captain_options")},
    "plans": plans, "teams": teams, "players": [slim(P[i]) for i in sorted(ids) if i in P],
    "league": {"name": "Sample mini-league", "size": lg["size"], "rows": rows},
    "chips": src["chips"], "accuracy": {k: src["accuracy"][k] for k in ("mae", "corr", "base_corr")},
}
OUT.write_text("// " + out["_label"] + "\nwindow.SAMPLE = " + json.dumps(out, separators=(",", ":")) + ";\n")
print("wrote", OUT, OUT.stat().st_size, "bytes,", len(out["players"]), "players")
