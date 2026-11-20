"""FL-165: unit and Python/JS parity tests for the optional falling banked-FT scale (off by default)."""
import json
import random
import subprocess
import unittest

import optimise


class TestFtScale(unittest.TestCase):
    def test_enabled_by_default(self):
        self.assertEqual(optimise.FT_SCALE, (2.0, 1.6, 1.3, 1.1))
        self.assertEqual(optimise.planner_settings(5)["ft_scale"], [2.0, 1.6, 1.3, 1.1])

    def test_ft_bonus_flat_and_scale(self):
        self.assertAlmostEqual(optimise.ft_bonus(1, ft_value=1.5, ft_scale=None), 1.5)
        self.assertAlmostEqual(optimise.ft_bonus(3, ft_value=1.5, ft_scale=None), 4.5)
        sc = (2.0, 1.6, 1.3, 1.1)
        expected = {1: 0.0, 2: 2.0, 3: 3.6, 4: 4.9, 5: 6.0}
        for ft_left, want in expected.items():
            self.assertAlmostEqual(optimise.ft_bonus(ft_left, ft_scale=sc), want, places=6)

    def test_invalid_ft_scale_raises(self):
        for bad in ((2.0, 1.6, 1.3), (1.0, 2.0, 1.3, 1.1), (2.0, 1.6, 1.3, -0.1)):
            with self.assertRaises(ValueError):
                optimise.ft_bonus(2, ft_scale=bad)

    def test_python_js_parity_with_ft_scale(self):
        sc = (2.0, 1.6, 1.3, 1.1)
        rng = random.Random(19)
        pos = ["GKP"] * 4 + ["DEF"] * 10 + ["MID"] * 10 + ["FWD"] * 6
        gws = [11, 12, 13, 14, 15]
        players = {}
        for k, p in enumerate(pos, start=1):
            base = rng.uniform(2.0, 6.0)
            players[k] = {
                "pos": p,
                "team": 1 + k % 15,
                "price": round(4.5 + base * 0.8, 1),
                "xp": {g: round(max(0.5, base + rng.uniform(-1.0, 1.0)), 2) for g in gws},
                "ok": True,
                "p10": {g: 0.1 for g in gws},
                "nailed": 100,
            }
        squad = [1, 2, 5, 6, 7, 8, 9, 15, 16, 17, 18, 19, 25, 26, 27]
        for i in squad:
            players[i]["xp"] = {g: 2.5 for g in gws}
            players[i]["price"] = 5.0
        r = optimise.solve(players, squad, {}, 2.0, 2, gws, max_hits=0, ft_scale=sc, time_limit=30)
        self.assertIsNotNone(r)
        self.assertLessEqual(r["ft_left"], 5)
        self.assertAlmostEqual(r["value"], round(r["xp_total"] + optimise.ft_bonus(r["ft_left"], ft_scale=sc), 2), places=2)

        rules = {**optimise.planner_settings(len(gws)), "ft_value": optimise.FT_VALUE, "ft_scale": list(sc)}
        payload = json.dumps({
            "players": {str(k): v for k, v in players.items()},
            "squad": squad,
            "gws": gws,
            "rules": rules,
            "bank": 2.0,
            "ft0": 2,
        })
        js = """
        import makeHighs from "./site/vendor/highs.js";
        import solver from "./site/plan-solver.js";
        const inp = JSON.parse(process.argv[1]);
        const players = Object.fromEntries(Object.entries(inp.players).map(([k, v]) => [+k, v]));
        const settings = solver.settingsFrom(inp.rules);
        const highs = await makeHighs();
        const r = await solver.solve(highs, { players, squad: inp.squad, sell: {}, bank: inp.bank, ft0: inp.ft0, gws: inp.gws, maxHits: 0, ...settings });
        console.log(JSON.stringify({ objective: r.objective, value: r.value, ftLeft: r.ftLeft }));
        """
        out = subprocess.check_output(["node", "--input-type=module", "-e", js, payload], text=True)
        jr = json.loads(out)
        self.assertAlmostEqual(jr["objective"], r["objective"], delta=0.05)
        self.assertAlmostEqual(jr["value"], r["value"], delta=0.05)


if __name__ == "__main__":
    unittest.main()
