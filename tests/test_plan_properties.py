"""Property tests: rules a squad and a transfer plan must never break, thrown many random leagues and squads.

CLAUDE.md doesn't say new dependencies may be added (requirements.txt is also what the hourly Refresh installs), so
this uses a small seeded generator (random.Random with fixed seeds) instead of Hypothesis. Each case is reproducible
from its seed, printed in the failure message, and the run is the same every time: no flakiness, no retries.

What is checked, by a checker written here and independent of optimise._check (so it also tests the safety net):
  - 15 players, 2 GK / 5 DEF / 5 MID / 3 FWD, no duplicates, every week
  - at most 3 from a club (a squad that already holds 4 after a real move may keep them only in a week without a
    transfer, FL-074)
  - a valid starting XI: 11 from the squad, 1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD; captain and vice in it and different;
    the bench is the other 4, keeper first
  - bank never below £0 across the plan, and the bank the plan reports is the money left after its moves (selling
    price for players you own, buying price otherwise); squad cost stays within the money you have
  - FPL free-transfer rules: hits = moves beyond free transfers, free transfers 1-5, rolled correctly; no more than
    MAX_MOVES_WEEK moves a week; max_hits respected (Balanced and Play safe: none)
  - the plan's totals add up (xp_total = XI + captain - 4 per hit, value = xp_total + FT value per banked FT)
And for strategy_plans: Balanced and Play safe never take a hit, Roll makes no move in week 1, Play safe gives up no
points and Chase rank at most CHASE_BUDGET against Balanced for the same option (CLAUDE.md, Tabs and planner).

Chip rules are the browser planner's (optimise.py carries no chips); they are in tests/plan-properties.mjs.
Missing: if optimise.solve finds no plan for a case built to have one, the test fails with the seed and LAST_FAIL.
"""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import optimise  # noqa: E402

POS_N = {"GKP": 8, "DEF": 22, "MID": 22, "FWD": 12}
PRICE = {"GKP": (4.0, 6.0), "DEF": (4.0, 7.5), "MID": (4.5, 12.5), "FWD": (4.5, 14.0)}
XI_MIN, XI_MAX = optimise.XI_MIN, optimise.XI_MAX
CASES = 14   # solve() cases; each takes a fraction of a second


def league(rng, gws):
    """A random league: 20 clubs, POS_N players a position, random prices and projections, ~8% not available."""
    players, k = {}, 0
    for pos, n in POS_N.items():
        for _ in range(n):
            k += 1
            lo, hi = PRICE[pos]
            price = round(rng.uniform(lo, hi), 1)
            base = rng.uniform(0.5, 2.0) + (price - lo) * rng.uniform(0.2, 0.6)
            players[k] = {"pos": pos, "team": rng.randint(1, 20), "price": price, "ok": rng.random() > 0.08,
                          "xp": {g: round(max(0.0, base + rng.uniform(-1.5, 1.5)), 2) for g in gws},
                          "p10": {g: round(rng.uniform(0, 0.3), 3) for g in gws}, "nailed": rng.choice([100, 100, 80, 40])}
    return players


def random_squad(rng, players, four_from=None):
    """A legal 15 (shape, 3 a club), or with four_from set, one that holds 4 from that club (a real move, FL-074)."""
    for _ in range(1000):
        squad, clubs = [], {}
        if four_from is not None:
            mine = [i for i, p in players.items() if p["team"] == four_from]
            if len(mine) < 4:
                return None
            squad = rng.sample(mine, 4)
            clubs[four_from] = 4
        need = {pos: n - sum(players[i]["pos"] == pos for i in squad) for pos, n in optimise.SHAPE.items()}
        if any(v < 0 for v in need.values()):
            continue
        ok = True
        for pos, n in need.items():
            cand = [i for i, p in players.items() if p["pos"] == pos and i not in squad and p["team"] != four_from]
            rng.shuffle(cand)
            for i in cand:
                if n == 0:
                    break
                t = players[i]["team"]
                if clubs.get(t, 0) < 3:
                    squad.append(i)
                    clubs[t] = clubs.get(t, 0) + 1
                    n -= 1
            ok = ok and n == 0
        if ok:
            return squad
    return None


def selling(rng, players, squad):
    """Selling prices at or a little below today's price (FPL keeps half the rise; a fall is taken in full)."""
    return {i: round(max(3.5, players[i]["price"] - rng.choice([0, 0, 0.1, 0.2, 0.3])), 1) for i in squad}


def problems(plan, players, squad, sell, bank, ft0, *, max_hits=None, week1_moves=None, ft_value=optimise.FT_VALUE):
    """Every rule the plan breaks, as text ([] if none). Independent of optimise._check."""
    out = []
    have, money, ft = set(squad), bank, ft0
    held = {}
    for i in squad:
        held[players[i]["team"]] = held.get(players[i]["team"], 0) + 1
    owned = set(squad)   # players whose selling price applies (bought back later: buying price again)
    total = 0.0
    for w, wk in enumerate(plan["weeks"]):
        g, ins, outs = wk["gw"], wk["in"], wk["out"]
        tag = f"GW{g}"
        if len(ins) != len(outs) or len(set(ins)) != len(ins) or len(set(outs)) != len(outs):
            out.append(f"{tag}: {len(ins)} in, {len(outs)} out")
        if not set(outs) <= have:
            out.append(f"{tag}: sells {sorted(set(outs) - have)} not owned")
        if set(ins) & have:
            out.append(f"{tag}: buys {sorted(set(ins) & have)} already owned")
        if any(not players[i]["ok"] for i in ins):
            out.append(f"{tag}: buys an unavailable player")
        for i in outs:
            money += sell[i] if i in owned else players[i]["price"]
            owned.discard(i)
        for i in ins:
            money -= players[i]["price"]
        have = (have - set(outs)) | set(ins)
        if money < -0.05:
            out.append(f"{tag}: bank below £0 (£{money:.1f}m)")
        if abs(money - wk["bank"]) > 0.051:
            out.append(f"{tag}: plan says bank £{wk['bank']}m, its moves leave £{money:.2f}m")
        if len(have) != 15:
            out.append(f"{tag}: {len(have)} players")
        for pos, n in optimise.SHAPE.items():
            c = sum(players[i]["pos"] == pos for i in have)
            if c != n:
                out.append(f"{tag}: {c} {pos}, not {n}")
        clubs = {}
        for i in have:
            clubs[players[i]["team"]] = clubs.get(players[i]["team"], 0) + 1
        for t, c in clubs.items():
            limit = 3 if ins else max(3, held.get(t, 0))
            if c > limit:
                out.append(f"{tag}: {c} from club {t}" + (" in a week with transfers" if ins else ""))
        xi, bench = wk["xi"], wk["bench"]
        if len(xi) != 11 or len(set(xi)) != 11 or not set(xi) <= have:
            out.append(f"{tag}: XI isn't 11 from the squad")
        for pos in optimise.SHAPE:
            c = sum(players[i]["pos"] == pos for i in xi)
            if not XI_MIN[pos] <= c <= XI_MAX[pos]:
                out.append(f"{tag}: {c} {pos} in the XI")
        if set(bench) != have - set(xi) or len(bench) != 4:
            out.append(f"{tag}: bench isn't the other 4")
        elif players[bench[0]]["pos"] != "GKP":
            out.append(f"{tag}: bench keeper isn't first")
        if wk["captain"] not in xi or wk["vice"] not in xi or wk["captain"] == wk["vice"]:
            out.append(f"{tag}: captain/vice not two different starters")
        n = len(ins)
        if w == 0 and week1_moves is not None and n != week1_moves:
            out.append(f"{tag}: {n} moves, asked for {week1_moves}")
        if n > optimise.MAX_MOVES_WEEK:
            out.append(f"{tag}: {n} moves, over the weekly cap")
        if wk["ft"] != ft:
            out.append(f"{tag}: plan says {wk['ft']} free transfers, FPL's rules give {ft}")
        hits = max(0, n - ft)
        if wk["hits"] != hits:
            out.append(f"{tag}: {wk['hits']} hits for {n} moves with {ft} FT (FPL: {hits})")
        if max_hits is not None and wk["hits"] > max_hits:
            out.append(f"{tag}: {wk['hits']} hits, allowed {max_hits}")
        ft = 1 if n > ft else min(5, ft - n + 1)
        pts = sum(players[i]["xp"].get(g, 0) for i in xi) + players[wk["captain"]]["xp"].get(g, 0)
        if abs(pts - wk["xp"]) > 0.011:
            out.append(f"{tag}: xp {wk['xp']} but XI + captain = {pts:.2f}")
        total += pts - optimise.HIT * wk["hits"]
    if plan["ft_left"] != ft:
        out.append(f"ft_left {plan['ft_left']}, FPL's rules give {ft}")
    if abs(plan["xp_total"] - total) > 0.05:
        out.append(f"xp_total {plan['xp_total']} but the weeks add up to {total:.2f}")
    if abs(plan["value"] - (plan["xp_total"] + ft_value * plan["ft_left"])) > 0.011:
        out.append(f"value {plan['value']} isn't xp_total + {ft_value} x ft_left")
    return out


def tempt(players, squad, gws, club=7):
    """Make breaking a rule pay: a club whose players you don't own are cheap and far better than anyone, so a plan
    that ignored the 3-a-club limit would load up on them. Without this, random leagues almost never test the limit."""
    for i, p in players.items():
        if p["team"] == club and i not in squad:
            p["price"], p["ok"] = PRICE[p["pos"]][0], True
            p["xp"] = {g: x + 6.0 for g, x in p["xp"].items()}
    for pos in optimise.SHAPE:   # enough of them that 4+ would fit the shape
        extra = [i for i, p in players.items() if p["pos"] == pos and i not in squad and p["team"] != club][:2]
        for i in extra:
            players[i]["team"] = club
            players[i]["price"], players[i]["ok"] = PRICE[pos][0], True
            players[i]["xp"] = {g: x + 6.0 for g, x in players[i]["xp"].items()}


def case(seed):
    """(players, squad, sell, bank, ft0, gws, settings) for one seed."""
    rng = random.Random(seed)
    gws = [11, 12, 13]
    players = league(rng, gws)
    squad = None
    if rng.random() < 0.25:
        squad = random_squad(rng, players, four_from=rng.randint(1, 20))
    squad = squad or random_squad(rng, players)
    if rng.random() < 0.4:
        tempt(players, squad, gws)
    sell = selling(rng, players, squad)
    bank = round(rng.uniform(0, 3), 1)
    ft0 = rng.randint(1, 5)
    max_hits = rng.choice([0, 1, None])
    # a week-1 move count the rules allow with these hits (FL-074: a squad over the club limit must fix it to move)
    week1 = rng.choice([None, None, 0, 1, 2])
    if week1 and max_hits is not None and week1 > ft0 + max_hits:
        week1 = ft0
    return players, squad, sell, bank, ft0, gws, {"max_hits": max_hits, "week1_moves": week1}


class SolvedPlansKeepTheRules(unittest.TestCase):
    def test_random_leagues(self):
        for seed in range(CASES):
            players, squad, sell, bank, ft0, gws, st = case(seed)
            with self.subTest(seed=seed, **st, ft0=ft0, bank=bank):
                plan = optimise.solve(players, squad, sell, bank, ft0, gws, time_limit=20, **st)
                self.assertIsNotNone(plan, f"seed {seed}: no plan ({optimise.LAST_FAIL[0]})")
                self.assertEqual(problems(plan, players, squad, sell, bank, ft0, **st), [], f"seed {seed}")

    def test_the_generated_squads_are_legal(self):
        # the generator itself: if it made illegal squads the tests above would prove nothing
        for seed in range(CASES):
            players, squad, *_ = case(seed)
            self.assertEqual(len(set(squad)), 15)
            for pos, n in optimise.SHAPE.items():
                self.assertEqual(sum(players[i]["pos"] == pos for i in squad), n)
            self.assertLessEqual(max(sum(players[j]["team"] == players[i]["team"] for j in squad) for i in squad), 4)


class StrategyRules(unittest.TestCase):
    def test_strategies_on_random_leagues(self):
        for seed in (101, 102, 103):
            rng = random.Random(seed)
            gws = [11, 12, 13]
            players = league(rng, gws)
            squad = random_squad(rng, players)
            for i in squad:   # a weak squad with one free transfer, so a -4 would pay: only Chase rank may take it
                players[i]["xp"] = {g: 0.5 for g in gws}
            sell = selling(rng, players, squad)
            bank, ft0 = round(rng.uniform(0, 2), 1), 1
            eo = {i: round(rng.uniform(0, 0.7), 3) for i in players}
            plans, notes = optimise.strategy_plans(players, squad, sell, bank, ft0, gws,
                                                   [("roll", 0), ("one", 1), ("two", 2)], eo=eo, time_limit=20)
            with self.subTest(seed=seed):
                self.assertIn("roll", plans, notes)
                for k, pl in plans.items():
                    mode = k.split("_")[0] if "_" in k else "balanced"
                    hits_ok = optimise.MAX_HITS[mode]
                    self.assertEqual(problems(pl, players, squad, sell, bank, ft0, max_hits=hits_ok), [], f"seed {seed} {k}")
                    if k.endswith("roll"):
                        self.assertEqual(pl["weeks"][0]["in"], [], f"seed {seed} {k}: Roll moves in week 1")
                    if mode in ("balanced", "safe"):
                        self.assertEqual(sum(w["hits"] for w in pl["weeks"]), 0, f"seed {seed} {k}: took a hit")
                    opt = k.split("_", 1)[1] if "_" in k else k
                    if mode != "balanced" and opt in plans and not pl.get("fallback"):
                        budget = optimise.SAFE_BUDGET + optimise.TIE if mode == "safe" else optimise.CHASE_BUDGET
                        self.assertGreaterEqual(pl["value"], plans[opt]["value"] - budget - 0.011,
                                                f"seed {seed} {k}: gives up more than {budget} against Balanced")


class SafetyNetAgrees(unittest.TestCase):
    """optimise._check (the re-check after every solve) must reject what the rules reject: random plans, most of them
    broken on purpose, judged by it and by the independent checker above."""

    def test_random_hand_made_plans(self):
        disagree = []
        for seed in range(300):
            rng = random.Random(10_000 + seed)
            gws = [11, 12]
            players = league(rng, gws)
            squad = random_squad(rng, players)
            sell = selling(rng, players, squad)
            bank = round(rng.uniform(0, 2), 1)
            weeks, have = [], list(squad)
            for g in gws:
                ins, outs = [], []
                for _ in range(rng.choice([0, 1, 1, 2])):
                    o = rng.choice(have)
                    same = [i for i, p in players.items() if p["pos"] == players[o]["pos"] and i not in have]
                    pick = rng.choice(same if rng.random() < 0.9 else list(players))   # sometimes the wrong position
                    if pick in have or pick in ins:
                        continue
                    have = [pick if x == o else x for x in have]
                    ins.append(pick)
                    outs.append(o)
                by = lambda pos: [i for i in have if players[i]["pos"] == pos]
                xi = (by("GKP")[:1] + by("DEF")[:4] + by("MID")[:4] + by("FWD")[:2]) if rng.random() < 0.9 else have[:11]
                bench = sorted(set(have) - set(xi), key=lambda i: players[i]["pos"] != "GKP")
                weeks.append({"gw": g, "in": ins, "out": outs, "xi": xi, "bench": bench,
                              "captain": xi[0] if xi else None, "vice": xi[1] if len(xi) > 1 else None})
            sp = {i: sell.get(i, players[i]["price"]) for i in players}
            buy = {i: players[i]["price"] for i in players}
            init = {i: int(i in squad) for i in players}
            theirs = optimise._check(weeks, players, squad, sp, buy, bank, init, (), ())
            ours = [p for p in self._rules_only(weeks, players, squad, sell, bank)]
            if (theirs is None) != (not ours):
                disagree.append(f"seed {10_000 + seed}: _check says {theirs!r}, rules say {ours}")
        self.assertEqual(disagree, [])

    @staticmethod
    def _rules_only(weeks, players, squad, sell, bank):
        """The FPL-rule part of problems(): what _check is responsible for (not FT bookkeeping or totals)."""
        plan = {"weeks": [dict(w, bank=0, ft=0, hits=0, xp=0) for w in weeks], "ft_left": 0, "xp_total": 0, "value": 0}
        skip = ("plan says bank", "free transfers", "hits for", "xp ", "ft_left", "xp_total", "value ", "unavailable",
                "bench keeper", "captain/vice", "XI in the", " in the XI", "moves, ")
        found = problems(plan, players, squad, sell, bank, 1)
        # _check tests the XI's size and that it plus the bench is the squad, not its formation, the vice or bench order
        return [p for p in found if not any(s in p for s in skip)]


if __name__ == "__main__":
    unittest.main()
