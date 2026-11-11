# External xMins model: evaluation (30 Oct 2026)

**Source:** user-supplied `original_xmins_model.joblib`. It holds four XGBoost models: start chance, minutes if he starts, bench-appearance chance and minutes from the bench. It has 21 inputs, all built from minutes history (last game, 3/5/10-gameweek averages, position, home/away, days since last game). It was trained on 2022-23 and 2023-24.
- **Safety:** checked with pickletools. The only imports are xgboost plus one custom class (`fpl_xmins.model.XMinutesModel`) that wasn't supplied. It was loaded with a whitelist unpickler and the four boosters were exported to plain XGBoost JSON (`xmins/*.json`, about 2.3 MB), so no pickle is ever loaded.
- **Reconstructed inputs:** the code that built the inputs wasn't supplied, so `xmins.py` rebuilds them from FPL live data before each gameweek. History rows are the gameweeks his club played and he had a row; double gameweeks are split by fixture count. Missing history is left as NaN, as in training.

**How it's wired in:** `params["xmins"]`, off by default. (Since adopted: on by default from PR #23, 30 Oct 2026; see `docs/model-log.md`. Note added 11 Nov 2026.)
- It replaces `p_start`, `p_sub`, `m_start` and `m_sub` in `project()`.
- Availability, European congestion, the return ramp and `p60_given_start` still come from FPL Lab.
- `xmins_combine` sets how the bench chance is combined:
  - "A": the bench chance is conditional on not starting.
  - "B": the bench chance is unconditional, capped at 1 − start chance. B is the recommended setting (less bias).

**New in backtest.py:** `minutes_eval()` scores minutes directly, on weeks where the player's club has one fixture.
- Error of expected minutes against real minutes (MAE, RMSE, bias).
- Brier score of start chance against whether he started, and of 60+ chance against whether he played 60+.
- Segments: position, back from absence, length of usable history, gameweek.
- `--params`, `--quick`, and minutes deltas in `--compare`.
- With defaults the headline matches main exactly.

## Results (variant B)

Minutes, players who played in the last 3 GWs. Lower is better.

| | Start Brier | 60+ Brier | xMin RMSE | xMin MAE |
|---|---|---|---|---|
| 2026/27 GW3-8, status log | 0.148 → 0.121 | 0.156 → 0.137 | 27.7 → 26.5 | 16.9 → 19.2 |
| 2025/26 (out of sample) | 0.182 → 0.145 | 0.182 → 0.157 | 31.0 → 29.3 | 20.5 → 22.3 |
| 2024/25 (out of sample) | 0.184 → 0.149 | 0.187 → 0.163 | 31.4 → 29.6 | 21.0 → 22.6 |

MAE rewards all-or-nothing guesses, so it gets worse for any properly calibrated expected value. RMSE and Brier are the fair scores here.

Players back from absence, 2026/27: start Brier 0.121 → 0.085 with the status log (0.223 → 0.092 without it).

Points, from bench.py:

| | corr | rank | MAE | RMSE |
|---|---|---|---|---|
| 2026/27 | 0.429 → 0.434 | 0.538 → 0.549 | 1.806 → 1.796 | 2.657 → 2.649 |
| 2025/26 | 0.387 → 0.403 | 0.484 → 0.503 | 1.887 → 1.867 | 2.750 → 2.725 |
| 2024/25 | 0.412 → 0.426 | 0.498 → 0.514 | 1.780 → 1.770 | 2.631 → 2.616 |

- Top-N picks were unchanged. Captain changes were within noise, apart from 2024/25 at +0.60 (CI +0.09 to +1.37).
- `--compare` flags, with the status log: top 30 projected, bias −0.27 and MAE +0.04. Base top-30 bias was over-projected at +0.25, so this mostly corrects it, though top-30 corr fell 0.02. Without the status log, flagged players' bias also moved by −0.43 (MAE −0.43, so better).

**Not covered by the external model:** new signings still get about 0.05 start chance, and players who played this week after missing the previous 3 got worse (start Brier 0.21 → 0.26, n=128). Domestic cup rotation still isn't modelled.

**To adopt:**
- Add `xgboost-cpu==3.4.1` to requirements (a 5.8 MB wheel; the plain `xgboost` package installs about 84 MB).
- Keep failing loudly if the model files are missing.
- Add a validate.py range check on xmin and p_start.
