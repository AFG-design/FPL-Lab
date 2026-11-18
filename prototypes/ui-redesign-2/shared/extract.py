"""Build prototypes/ui-redesign-2/shared/sample-data.js from a published FPL LAB data.json + data-extra.json.

    python3 -I prototypes/ui-redesign-2/shared/extract.py PATH/TO/data.json PATH/TO/data-extra.json

Prototype-only (round 2 of the UI redesign). Reads a snapshot of the files the live site publishes (public FPL API data,
Understat and odds as build.py already joins them; no FPL Review data) and writes a trimmed, read-only sample for the
three design prototypes. Mini-league managers are anonymised. Nothing in site/, build.py or the workflows uses this.
Missing input fails loudly (KeyError / FileNotFoundError); there are no silent defaults. A player with no extra detail
(data-extra.json has no row for them) gets "detail": null, and the prototypes show "No breakdown" rather than zeros.
"""
import json, sys
from pathlib import Path

src = json.load(open(sys.argv[1]))
extra = json.load(open(sys.argv[2]))["players"]
OUT = Path(__file__).with_name("sample-data.js")
meta, mgr = src["meta"], src["manager"]
gws = [str(g) for g in meta["plan_gws"]]
teams = {int(k): {"short": t["short"], "name": t["name"], "code": t["code"],
                  "fx": {g: [[f["opp"], f["home"], f["fdr"]] for f in t["fx"].get(g, [])] for g in gws}}
         for k, t in src["teams"].items()}
P = {p["id"]: p for p in src["players"]}
squad_ids = [s["id"] for s in src["squad"]]


def slim(p):
    e = extra.get(str(p["id"]))
    return {"id": p["id"], "name": p["name"], "full": p["full"], "team": p["team"], "pos": p["pos"], "price": p["price"],
            "own": p["own"], "form": p["form"], "pts": p["pts"], "xg": p["xg"], "xa": p["xa"], "xgi90_4": p["xgi90_4"],
            "xg90": p["xg90"], "xa90": p["xa90"], "nailed": p["nailed"], "start": p["start_next"], "xmin": p["xmin"],
            "status": p["status"], "news": p["news"], "chance": p["chance"], "xp": {g: p["xp"].get(g) for g in gws},
            "xp1": p["xp1"], "xp5": p["xp5"], "sp": [k for k, v in (p.get("sp") or {}).items() if v], "tin": p["tin"],
            "tout": p["tout"], "goals": p["goals"], "assists": p["assists"], "cs": p["cs"], "bonus": p["bonus"],
            "mins": p["mins"], "pts4": p["pts4"], "dist": p["dist"].get(gws[0]), "price_proj": p.get("price_proj"),
            "detail": None if e is None else {"xp": e["xp_detail"], "pts": e["s_pts"], "min": e["s_min"], "xgi": e["s_xgi"]}}


top = sorted((p for p in src["players"] if p.get("ok")), key=lambda p: -p["xp5"])[:90]
ids = {p["id"] for p in top} | set(squad_ids)
for pid in src["recommended"].values():
    for w in src["plans"][pid]["weeks"]:
        ids |= set(w["in"]) | set(w["out"])
plans = {}
for strat, pid in src["recommended"].items():
    pl = src["plans"][pid]
    plans[strat] = {"vs_none": pl["vs_none"], "xp_total": pl["xp_total"], "ft_left": pl["ft_left"],
                    "weeks": [{k: w[k] for k in ("gw", "in", "out", "xi", "bench", "captain", "vice", "ft", "hits", "bank", "xp")} for w in pl["weeks"]]}
lg = src["crowd"]["leagues"][0]
rows = []
me_at = next((i for i, r in enumerate(lg["rows"]) if r["me"]), None)
keep = max(12, me_at + 1) if me_at is not None and me_at < 25 else 12   # every row down to yours, so "nearest rival" is true
for i, r in enumerate(lg["rows"][:keep]):
    rows.append({"name": "You" if r["me"] else f"Rival {chr(65 + i)}", "team": mgr["team"] if r["me"] else f"Sample FC {i + 1}",
                 "me": r["me"], "rank": r["rank"], "last": r["last_rank"], "total": r["total"], "gw": r["gw_pts"],
                 "chip": r["chip"], "cap": next((pid for pid, m in r["picks"] if m >= 2), None),
                 "picks": [pid for pid, m in r["picks"] if m >= 1]})
if not any(r["me"] for r in rows):    # you are outside the top 12: add your own row (rank from the league, not assumed)
    rows.append({"name": "You", "team": mgr["team"], "me": True, "rank": lg["my_rank"], "last": lg["my_rank"],
                 "total": mgr["points"], "gw": mgr["gw_points"], "chip": None, "cap": src["lineup"]["captain"],
                 "picks": src["lineup"]["xi"]})
acc = src["accuracy"]
src_rows = [(k, v.get("built"), {kk: v[kk] for kk in ("matches", "players", "gw", "fixtures") if kk in v}) for k, v in src["sources"].items()]
out = {
    "_label": "SAMPLE DATA: FPL LAB snapshot of " + meta["built"] + " (public FPL API). Mini-league managers anonymised. Prototype only.",
    "meta": {k: meta[k] for k in ("built", "next_gw", "cur_gw", "deadline", "picks_gw")},
    "manager": {k: mgr[k] for k in ("team", "points", "rank", "gw_points", "bank", "value", "free_transfers", "total_players")},
    "history": src["history"], "gws": [int(g) for g in gws],
    "squad": src["squad"], "lineup": {k: src["lineup"][k] for k in ("xi", "bench", "captain", "vice", "xp_best", "captain_options")},
    "plans": plans, "teams": teams, "players": [slim(P[i]) for i in sorted(ids) if i in P],
    "league": {"name": "Sample mini-league", "size": lg["size"], "my_rank": lg["my_rank"], "rows": rows},
    "accuracy": {"mae": acc["mae"], "corr": acc["corr"], "base_corr": acc["base_corr"], "rmse": acc["rmse"],
                 "base_rmse": acc["base_rmse"], "n": acc["n"], "weeks": acc["weeks"], "buckets": acc["buckets"]},
    "rating": {"best": src["rating"]["best"]["weeks"], "field": src["rating"]["field"]},
    "deadlines": src["week"]["deadlines"][:8],
    "health": {"ok": src["health"]["ok"], "errors": src["health"]["errors"], "warnings": src["health"]["warnings"], "sources": src_rows},
}
OUT.write_text("// " + out["_label"] + "\nwindow.SAMPLE = " + json.dumps(out, separators=(",", ":")) + ";\n")
print("wrote", OUT, OUT.stat().st_size, "bytes,", len(out["players"]), "players")
