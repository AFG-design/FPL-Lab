# Player odds log

Results of testing The Odds API player odds (collected by `odds_players.py` since GW8) in the FPL Lab model. See also `docs/model-log.md`.

## 26 Oct 2026 — GW8 check: player odds blend (one gameweek, a hint only)
- Odds: The Odds API deadline snapshot (history/player_odds_gw8.json, 426 players, 10 fixtures, US books).
  Blend: odds goals = -ln(1 - p_score), assists = -ln(1 - p_assist), scaled so each team sums to the
  model's team expected goals (x0.97; assists x0.75 per goal), times the model's appearance chance gated by
  the live pre-deadline xP; delta applied to the live GW8 xP (history/proj_gw8.json) with slope 0.86.
- Pool: 372 players who played in GW5-7 (331 priced). Live FPL Lab: MAE 1.873, corr 0.374, rank 0.436,
  top-5 7.6, top-10 4.8, captain Haaland 8. With odds 25/50/75/100%: corr 0.376-0.377 (+0.003), MAE
  1.875-1.890 (worse), rank 0.436-0.431 (flat to worse), top-10 5.1-5.2; captain switched to Gabriel (17,
  a DEF haul — luck). Priced MID/FWD only (209): MAE 1.474 -> 1.484/1.503, rank 0.475 -> 0.470/0.463,
  top-5 2.8 -> 2.8/2.0. FPL ep_next: MAE 2.288, corr 0.193, rank 0.326 (FPL Lab far better).
- GW8 bonus may still be provisional (event not marked finished at 09:50 UTC 26 Oct).
- Verdict: no sign of a gain at this crude blend. Not worth paying for the historical month yet; keep
  collecting (free) and re-test at ~GW12-13 with 5 gameweeks, or try odds only for start chance/minutes.
