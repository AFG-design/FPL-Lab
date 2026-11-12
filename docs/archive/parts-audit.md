# Missed-improvement audit (30 Oct 2026)

**Question:** after xMins, were other ideas dropped or missed because the test measured the wrong thing (total points only, 1 GW ahead only, a narrow player pool)?

**Method:**
- Every tested-and-rejected entry in model-log.md was checked for that pattern.
- New scratch tools (scratchpad, not in the repo):
  - `parts_eval.py` scores each scoring part separately, using raw pre-calibration projected points against real points from that part. Single-fixture weeks, pool = played in the last 3 GWs.
  - `horizon_eval.py` judges settings on 5-GW totals, which is what the planner uses.
  - `sim_eval.py` compares the simulated spread against the real one.
- Research switches were added on a local branch only (`parts-audit`, not pushed): `dc_cal`, `assist_pos`.

## 1. Part-by-part, current model with xMins on (projected / real points per player-week)

| Part | 2026/27 GW3-8 | 2025/26 | 2024/25 |
|---|---|---|---|
| Minutes | 1.32 / 1.28 | 1.37 / 1.30 | 1.35 / 1.29 |
| Goals | 0.34 / 0.31 | 0.33 / 0.34 | 0.34 / 0.35 |
| Assists | 0.17 / 0.19 | 0.17 / 0.19 | 0.18 / 0.20 |
| Clean sheets | 0.34 / 0.40 | 0.38 / 0.33 | 0.34 / 0.31 |
| Defensive contribution (DC) | 0.14 / 0.19 | 0.14 / 0.20 | (none) |
| Bonus | 0.14 / 0.17 | 0.14 / 0.17 | 0.14 / 0.16 |

- **Forwards' assists** are about half of real in every season: 0.10 projected against 0.19-0.23 real.
- **Top-30 bonus** is about 25% low: 0.31 against 0.44 (2025/26) and 0.38 against 0.49 (2024/25).
- **DC chance in 60+ games** is too low in every band:

  | Model chance | Real rate, DEF | Real rate, MID |
  |---|---|---|
  | about 4% | 15% | — |
  | about 2% | — | 9% |
  | 25% | 42% | — |

  The likely cause is the Poisson tail in `p_at_least(dc90 ...)`: DC counts vary more from game to game than a Poisson assumes. It isn't caused by gating on 60+ minutes, since only 0.5-1.4% of DC hits come in games under 60 minutes.

**Fixes tested (bench.py, three seasons):**
- **Settings:** `dc_cal` (0.07, 1.0); `assist_pos` FWD 1.75; `bonus_scale` 0.97; and all three together.
- **Points:** corr changed by at most ±0.001 in every season, and picks, captain and top-5 CIs all span 0. Bias rises by 0.05-0.12, which the global calibration would absorb.
- **Why nothing changes:** these are level errors (a whole group off by about the same amount). The global calibration (0.86 × raw + 0.33 × P(appears)) already compensates, so rankings don't change. This confirms the 22 Oct "per-part calibration" note.
- **They still matter for shown numbers:** the DC chance (`dc_rate`), the xP breakdown and haul chances.
- **The crude DC fix overshoots:** it pushes top-30 DC to 0.48 against 0.30 real, and gives forwards 0.06 against 0.01. A proper fix is position-specific and overdispersed (negative binomial), not a flat add-on.

## 2. Horizon: settings tuned 1 GW ahead, judged on 5-GW totals (2025/26, 2024/25)

| Change | corr | Picks (5-GW points) |
|---|---|---|
| xMins off | −0.022 / −0.016 | −0.30 (CI −0.55 to −0.04) / −0.13 |
| `recency` 0.9 | +0.001 / +0.004 | CIs span 0 |
| `recency` 0.7 | — | worse |
| `team_recency` 0.96 | +0.000 / +0.001 | +0.03 / +0.115 (2024/25 CI +0.01 to +0.22) |
| `min_recency` 0.6 | — | nil |

- The xMins gain is larger at 5 GWs than at 1 GW.
- Verdict: the 1-GW tuning holds up at 5 GWs. There's a slight lean to slower recency for planning (Coin flip; re-test with odds in archive seasons).

## 3. Simulated outcome spread (2025/26, sim 400, single-fixture weeks)

| | Real variance | Simulated | Formula |
|---|---|---|---|
| All players, xMins on | 7.44 | 5.64 | 6.81 |
| All players, xMins off | 7.59 | 5.44 | 6.91 |
| xP 4.5+, xMins on (n=44) | 17.7 | 17.2 | 15.6 |

- Blank Brier: 0.1837 with xMins off, 0.1794 with it on.
- xMins narrowed the gap a little. The simulation is still too narrow for the field, but for high-xP players it now fits better than the formula (small sample). Marginal: re-check over a full season before letting Play safe / Chase use the simulation.

## 4. Who the backtest scores

- Players who played but not in the previous 3 GWs (new signings, returners) make up about 6% of appearances and 3.5% of points.
- They aren't in the points backtest pool. The model projects 0.03 points for them with xMins off and 0.35 with it on, against 1.6-1.75 real.
- Small and hard to predict without flags. Add an "all players" line to bench output so changes for them are visible. (Done in FL-137: `bench.py` prints it under each model line.)

## Verdict

Minutes was the only large miss. Nothing else of that size was hidden by the points-only test.

**Worth doing:**
- Make part-level scoring permanent in backtest.py.
- Fix the DC chance properly (an overdispersed distribution, position-specific) for accurate displayed numbers.
- Report 5-GW-ahead results alongside 1-GW in bench.py.
