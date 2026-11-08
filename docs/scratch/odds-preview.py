# Research only: scratch script from the 23 Oct 2026 player-odds preview. Not part of the app.
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from odds_players import load_json
import bench
from fplmodel import project, POS, availability
cur = bench.current_ctx()
res = project(cur, 8, 1)
P = res["players"]; up = res["upcoming"]; el = cur["elements"]; sc = cur["scoring"]
od = load_json(ROOT / "odds/players.json")
SLOPE, W = 0.86, 0.5
rows = []
for fid, f in od["fixtures"].items():
    for tid in (f["h"], f["a"]):
        tf = up[tid].get(8, [])
        if not tf: continue
        team_mu = tf[0][2]
        pa = lambda pid: min(1.0, P[pid]["p_start"] + P[pid]["p_sub"]) * availability(el[pid], 0)
        pl = [(int(pid), v) for pid, v in f["players"].items() if int(pid) in el and el[int(pid)]["team"] == tid and "p_score" in v and int(pid) in P]
        lam = {pid: -math.log(1 - v["p_score"]) for pid, v in pl}
        tot = sum(lam[pid] * pa(pid) for pid, _ in pl)
        k = team_mu * 0.97 / tot if tot else 0
        # Legacy p_assist was mixed raw/fair; this research rescaling treats it as margin-bearing.
        lama = {pid: -math.log(1 - v.get("p_assist_raw", v.get("p_assist"))) for pid, v in pl if v.get("p_assist_raw", v.get("p_assist"))}
        tota = sum(lama[pid] * pa(pid) for pid in lama)
        ka = team_mu * 0.75 / tota if tota else 0
        for pid, v in pl:
            r = P[pid]; pos = POS[el[pid]["element_type"]]; d = r["detail"][8]
            g_m = d.get("goals", 0) / sc["goals_scored"][pos]; a_m = d.get("assists", 0) / sc["assists"]
            g_o = k * lam[pid] * pa(pid); a_o = ka * lama[pid] * pa(pid) if pid in lama else a_m
            delta = SLOPE * W * ((g_o - g_m) * sc["goals_scored"][pos] + (a_o - a_m) * sc["assists"])
            rows.append((el[pid]["web_name"], pos, r["xp"][8], r["xp"][8] + delta, delta, v["p_score"]))
mine = {"Raya","Konsa","Calafiori","Hall","Palmer","Rogers","Groß","Gibbs-White","Haaland","Calvert-Lewin","João Pedro","Dubravka","van Ewijk","De Cuyper","Slater"}
print("TOP 10 with odds")
for r in sorted(rows, key=lambda r: -r[3])[:10]: print(f"  {r[0]:14} {r[1]} {r[2]:5.2f} -> {r[3]:5.2f} ({r[4]:+.2f}) score {r[5]:.0%}")
print("YOUR SQUAD")
for r in sorted([r for r in rows if r[0] in mine], key=lambda r: -r[3]): print(f"  {r[0]:14} {r[1]} {r[2]:5.2f} -> {r[3]:5.2f} ({r[4]:+.2f})")
s = sorted(rows, key=lambda r: r[4]); print("RISERS", [(r[0], round(r[4], 2)) for r in s[-5:][::-1]]); print("FALLERS", [(r[0], round(r[4], 2)) for r in s[:5]])
