# AFG suggestion log

The AFG suggestion is a fan's-eye punt layer on top of the model (`afg.py`, AFG tab). It never changes
`fplmodel.py` or the optimiser. This log records what was tested, so the weights aren't set blindly.

## 23 Oct 2026 — built (PR #8)
- Factors: record v opponent, record at the ground (away games), home/away split, club head-to-head
  for GKP/DEF, hot run (returns in last 3 starts, +0.25), European week (−0.15), new manager (+0.2, from
  `afg_manual.json`). Derbies and former clubs shown, not scored.
- Records use "points beyond expectation": points in a 60+ min game − his own season average − the
  position × opponent × venue average that season. Shrinkage k: opponent 10, ground 10, split 15,
  club 8 meetings. Each nudge capped ±1.0, total ±1.5 a game, scaled by min(1, xmin/75).
- Data: vaastav archive 2019/20–2025/26 summarised into `afg/records.json` (weekly via priors.yml),
  plus this season from the FPL API at each build. Everton's ground split at 2025/26 (Goodison → Hill
  Dickinson).

## Signal test (2019/20–2025/26, ~55,000 starts, records from earlier seasons only)
- Player v opponent: corr −0.004 (attackers +0.006, defence −0.015). At away ground +0.004. At home
  ground +0.004. Home/away split +0.000. Club v opponent (defence) +0.003. All ≈ 0.
- Derbies: +0.00 pts/game beyond expectation (4,494 starts). Former club: −0.22 (se 0.13, 492 starts).
- Within-season residuals look negatively correlated, but that's an artefact of using the same
  season's average as the baseline; only cross-season tests are fair.

## Backtest on 2025/26 (`python3 afg.py backtest`, GW4–38)
- Captain (top AFG pick overall v top model pick): 454 v 460 pts, different pick in 17 of 35 weeks.
- Top-10 picks: 1,625 v 1,736 pts. Average miss per player 1.899 v 1.887.
- Nudges of 0.4+ in the right direction: 1,299 of 2,589 (50.2%) — a coin flip.

## Scoreboard
- Each build before the deadline saves `history/afg_gw{N}.json` (AFG captain, XI, punts with the
  model's like-for-like alternative, and model v AFG xP per player). After the GW, build.py scores
  captain points, XI points, punts v the model's swap, nudges right, and average miss.
- GW8 snapshot committed with the PR (built 23 Oct 16:43): AFG captain Palmer, model Haaland.
- Revisit the weights once there are 6–8 scored weeks.
