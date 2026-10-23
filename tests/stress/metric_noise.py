#!/usr/bin/env python3
"""How noisy are bench.py's decision metrics? Paired bootstrap over gameweeks for a tiny change (pen_xg 0.05 -> 0)
and the null spread of 'captain points' (cap1) when the top two projections are near-ties."""
import random, statistics as st
from common import *
A, TA = arch()
G = range(4, 39)
base = run_ctx(A, G, team_at=TA); alt = run_ctx(A, G, {"pen_xg": 0.0}, team_at=TA)
def cap(rows): return sorted(rows, key=lambda r: -r[2])[0][3]
def top5(rows): t = sorted(rows, key=lambda r: -r[2])[:5]; return sum(r[3] for r in t) / 5
d_cap = [cap(alt[g]) - cap(base[g]) for g in G]; d_t5 = [top5(alt[g]) - top5(base[g]) for g in G]
print("weeks where the captain pick changed:", sum(1 for g in G if sorted(alt[g], key=lambda r: -r[2])[0][0] != sorted(base[g], key=lambda r: -r[2])[0][0]))
random.seed(1)
def ci(d):
    bs = sorted(sum(random.choice(d) for _ in d) / len(d) for _ in range(5000))
    return round(sum(d) / len(d), 2), round(bs[125], 2), round(bs[4875], 2)
print("cap1 delta (mean, 95% CI):", ci(d_cap)); print("top5 delta (mean, 95% CI):", ci(d_t5))
gaps = [sorted((r[2] for r in base[g]), reverse=True)[:2] for g in G]
print("median gap between top-2 projections:", round(st.median(a - b for a, b in gaps), 2), "pts")
sd = st.pstdev([cap(base[g]) for g in G])
print(f"SD of captain points per GW {sd:.2f} -> SE of a 35-GW mean ~{sd/35**0.5:.2f}; a paired swap of ~1/3 of weeks gives SE ~{sd*(2*(1/3))**0.5/35**0.5:.2f}")
