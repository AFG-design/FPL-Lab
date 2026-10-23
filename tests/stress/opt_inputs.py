"""Builds a realistic optimiser input (GW8-12) shaped like build.py's opt_players. Used by optimiser_stress.py."""
import os, json
from common import *
from fplmodel import availability

GWS = None
def build(sim=1000, horizon=5):
    c = cur_ctx(); L = cur_last(); nxt = L + 1
    res = project(c, nxt, horizon, {"use_flags": True, "sim": sim})["players"]
    el = c["elements"]
    players = {}
    for pid, e in el.items():
        r = res.get(pid)
        if not r: continue
        xp = {g: round(v, 2) for g, v in r["xp"].items()}
        nailed = int(round(100 * r["p_start"] * min(1.0, r["m_start"] / 85) * availability(e, 0)))
        ok = bool(e["can_select"]) and e["status"] in ("a", "d") and r["xmin_base"] > 10
        players[pid] = {"pos": POS[e["element_type"]], "team": e["team"], "price": e["now_cost"] / 10, "xp": xp, "ok": ok,
                        "p10": {g: d["p10"] for g, d in (r.get("dist") or {}).items()}, "nailed": nailed}
    squad = json.load(open(os.path.join(ROOT, "tests/stress/my_squad.json")))
    sell = {i: players[i]["price"] for i in squad}
    gws = list(range(nxt, nxt + horizon))
    return c, players, squad, sell, 0.5, gws

def crowd_eo():
    cr = json.load(open(os.path.join(ROOT, "crowd/latest.json")))
    src = cr["near"] if cr["near"]["n"] >= 100 else cr["top10k"]
    return {int(k): v / 100 for k, v in src["eo"].items()}, {int(k): v for k, v in src["eo"].items()}
