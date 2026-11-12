# FPL Lab model log

What has been tested on the projection model, with results, so ideas aren't re-tried blindly.
Test bench: `bench.py` (rolling-origin backtest on this season, 2025/26 and 2024/25; past seasons carry betting odds
from odds/archive/ since PR #24, 31 Oct 2026).

## 12 Nov 2026 — FL-093: returning players stay in the projected list (Adopt as Marginal)

- Known error (FPL Review comparison, 6 Nov): Saliba, Minteh and Mitoma were missing from data.json. Cause:
  build.py lists a player only with minutes this season, 3+ xP over 5 GWs, or in the squad (`keep`), so a regular out
  all season drops out. Of FPL's 672 players on 12 Nov, 206 were left out: 97 unavailable ('u', mostly left the
  club), 83 available with no minutes (youth and back-up players), 24 injured, 2 doubtful.
- Fix: `fplmodel.returning` keeps a not-yet-listed player when FPL cleared him after flagging him this season ("back",
  from the news history), gives a chance above 0 ("chance"), or gives a return date inside the 5-GW window ("date").
  His start chance stays the model's and is marked `start_assumed`; the player sheet says so. 12 Nov: +6 players
  (Saliba, Butland, Anselmino back; Dasilva, Gyabi chance; Mitoma date), 466 → 472.
- Backtest and bench identical to main on every metric (projections unchanged; only list membership). MAE 1.8111 /
  1.7625; 5-GW picks 18.18 / 19.13 / 19.01; every paired CI [0, 0].
- Finding for the minutes model (not changed here): a regular back from a season-long absence gets almost no start
  chance (Saliba 2,614 minutes last season, start chance 1%, 0.34 xP over 5 GWs) because this season has no starts to
  go on. Belongs with FL-030 / FL-094.
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal.
## 12 Nov 2026 — FL-092: upcoming fixture odds from The Odds API (Adopt as Marginal)

- Known error (audit C7, still true for GW10): the fixture-odds blend (direct_w 0.85) never ran live, because
  odds/odds.json had no upcoming matches (football-data's fixtures.csv lists them only days ahead).
- Fix: odds.py takes one bulk h2h + totals snapshot from The Odds API (one region, 2 credits) at the 72/24/3 h
  checkpoints, converts it as before (margin removed per bookmaker, median, Poisson fit) and saves each snapshot to
  history/fixture_odds_gw{N}.json. The latest snapshot supplies the upcoming rows; football-data still supplies played
  matches and any fixture the snapshot lacks. Built on FL-112 (PR #120).
- Credits: 6 per gameweek here + about 60 for odds_players.py = 66; the busiest month (6 GWs) is about 396 of the
  free 500, and both scripts stop at 40 left.
- Backtest and bench: identical to main on every metric (no model code changed; backtests already give GW k its own
  pre-match odds). Same tables as FL-112: MAE 1.8111 / 1.7625 (without / with status log); 5-GW picks 18.18 / 19.13 /
  19.01, every paired CI [0, 0].
- What live gains (GW k projected from data before k, with v without GW k's own odds, use_flags off):
  GW8 MAE 1.7686 → 1.7677, GW9 1.5844 → 1.5796, GW10 1.7568 → 1.7492; mean |Δ xP| 0.04-0.06, largest ±0.38.
- Not measured: a live build with a real snapshot (the key is a GitHub secret; the API host is blocked in the dev
  session). A stand-in reply ran end to end: 10/10 GW11 fixtures matched, 0 validate errors.
- Decision: CI includes zero (bench can't see live inputs), fixes a known error, no segment worse → Adopt as
  Marginal. Re-check: after the first deadline, confirm history/fixture_odds_gw*.json has all three snapshots and
  Health shows the credits left.

## 12 Nov 2026 — FL-112: odds file holds one row per fixture (Adopt as Marginal)

- Known error (audit A6, 10 Nov): football-data.co.uk's fixtures.csv keeps listing a match after it is played, so
  every GW10 match was in odds/odds.json twice (played + upcoming): 110 rows, 10 fixture ids duplicated. GW10 counted
  twice in the market team ratings, and Health reported 10 upcoming odds when there were none.
- Fix: `odds.one_row_per_fixture` drops an upcoming row once FPL marks its fixture finished, then keeps one row per
  fixture id (played beats upcoming). odds.py writes the file that way and `fplmodel.prepare` applies the same rule to
  whatever file it gets, so an old or un-rewritten file can't double-count. validate.py warns about extra rows in the
  file. FPL `finished` missing = not finished (row kept). Re-run on 12 Nov: 110 → 100 rows, 0 upcoming.
- Baseline main `a8f877b`, frozen API responses to GW10, same priors, status log and archive odds both sides; the
  "after" side uses the committed odds file passed through the fix.
- Backtest (GW3–10, n=3,050), without / with status log: MAE 1.8111 → 1.8111 / 1.7625 → 1.7625, corr .4301 → .4301 /
  .4439 → .4439. Every segment, minutes figure and raw part identical; no flags. Expected: a backtest GW k only uses
  odds before k, and the duplicate rows were all GW10, so only live GW11+ ratings move.
- bench.py, before → after (identical; every paired CI [0, 0], captain changed 0/8, 0/35, 0/35):

| Season | 1-GW MAE | 1-GW corr | 1-GW picks | 5-GW corr | 5-GW picks |
|---|---|---|---|---|---|
| 2026/27, GW3–10 | 1.763 → 1.763 | .444 → .444 | 4.35 → 4.35 | .583 → .583 | 18.18 → 18.18 (4 origins) |
| 2025/26 | 1.858 → 1.858 | .411 → .411 | 4.45 → 4.45 | .523 → .523 | 19.13 → 19.13 |
| 2024/25 | 1.763 → 1.763 | .428 → .428 | 4.22 → 4.22 | .557 → .557 | 19.01 → 19.01 |

- Live GW11 (same code, old v cleaned odds file): mean |Δ| 0.003 xP next GW, 0.009 over 5 GWs; largest 5-GW move
  ±0.10 (defenders of clubs whose GW10 match was double-counted: Ajer, Hall, Kayode +0.10, Gabriel −0.10).
- Decision: CI includes zero (exactly 0), fixes a known error, no segment worse → Adopt as Marginal. Re-check: none
  needed beyond confirming Health shows 0 upcoming odds the morning after each gameweek.

## 9 Nov 2026 — FL-081: invalid return dates no longer crash projections

- Baseline: main `2377fcc`; identical frozen GW3–9 API responses, priors, status log and archive odds
  used for both implementations. Invalid calendar dates in FPL return-date news now emit a warning and use
  the existing unknown-return treatment, with recovery estimates marked assumed. No replacement day is
  invented. Year inference happens before date construction, allowing December 2023 news to refer to
  29 February 2024. Normal valid dates and the 60-day rollover rule are unchanged.
- Backtest without status log: MAE 1.810144 → 1.810144, corr .429364 → .429364, bias -.039818 → -.039818.
  With status log: MAE 1.764375 → 1.764375, corr .442675 → .442675, bias -.086012 → -.086012 (n=2,673).
  All JSON metrics, segments, minutes metrics and raw scoring parts compare exactly equal; no threshold flags.
- `bench.py` functions run separately against baseline and candidate code, including 1-GW and 5-GW totals:

| Season | 1-GW MAE before → after | 1-GW corr before → after | 1-GW picks before → after | 5-GW corr before → after | 5-GW picks before → after |
|---|---|---|---|---|---|
| 2026/27, GW3–9 | 1.764 → 1.764 | .443 → .443 | 4.21 → 4.21 | .598 → .598 | 18.13 → 18.13 |
| 2025/26 | 1.858 → 1.858 | .411 → .411 | 4.45 → 4.45 | .523 → .523 | 19.13 → 19.13 |
| 2024/25 | 1.763 → 1.763 | .428 → .428 | 4.22 → 4.22 | .557 → .557 | 19.01 → 19.01 |

Every metric and per-GW/per-origin value is identical. Paired bootstrap 95% CIs for captain, top-five and
1-GW picks are [0, 0] in all three seasons; 5-GW picks differences are also exactly zero, CI [0, 0].
Captains changed in 0/7, 0/35 and 0/35 weeks. These historical runs do not exercise malformed news dates
(the backtest uses flags from the status log, not current news); dedicated invalid-date and full-projection
regression tests establish the crash fix and assumed labels. Fresh live build: 470 players, GW11, validation
0 errors and three existing warnings (assumed GW8/GW9 targets and missing GW11 fixture odds).

## 8 Nov 2026 — FL-062: team ratings skip unfinished matches

- Baseline: main `6664c58`; frozen public API responses through finished GW9, shared unchanged by both runs.
  Live 0–0 scores were being treated as results even though the team's cumulative GW xG had been stripped by
  `finished_only`. In the deterministic regression, team 1's unblended attack fell 1.010369 → 0.943747 at kick-off;
  the fix keeps it exactly 1.010369. This is a live-data correctness fix, not a fitted parameter change.
- One shared unfinished-team/GW rule now drives `build.finished_only` and `prepare`. A team with any unfinished
  fixture contributes none of that GW's player stats, team xG or opponent-adjustment history. `team_ratings` requires
  `finished` and excludes a completed fixture if either side still has a match outstanding in that GW: its xG
  against cannot be recovered from the other team's incomplete cumulative total. Fully completed teams elsewhere
  in the GW still count. Both matches of a double enter once the team has completed them.
- Missing/false `finished`, including provisional-only completion, means wait for confirmed completion; scores
  alone never establish it. Missing scores on a finished fixture are still skipped. No zero-xG substitute, no
  historical data rewritten, and no change to the pre-match betting-market blend.

Backtest (`backtest.py raw --json ...` and `--status-log`, then `--compare`; GW3–9, n=2,673):

| Status log | MAE before → after | Correlation before → after | Bias before → after |
|---|---|---|---|
| Without | 1.810144 → 1.810144 | 0.429364 → 0.429364 | -0.039818 → -0.039818 |
| With | 1.764375 → 1.764375 | 0.442675 → 0.442675 | -0.086012 → -0.086012 |

The complete JSON metrics are identical in each comparison, including every segment, minutes accuracy and raw
scoring part. No threshold flags and nothing moved. Minutes MAE (without/with log): 20.01/19.04;
start Brier .1236/.1184; 60+ Brier .1390/.1343, all unchanged.

`bench.py` functions run separately against baseline and candidate code, with identical frozen inputs, archive
odds and default parameters; 1-GW and 5-GW metric dictionaries compare exactly equal on all three seasons:

| Season | 1-GW MAE before → after | 1-GW corr before → after | 1-GW picks before → after | 5-GW corr before → after | 5-GW picks before → after |
|---|---|---|---|---|---|
| 2026/27, GW3–9 | 1.764 → 1.764 | .443 → .443 | 4.21 → 4.21 | .598 → .598 | 18.13 → 18.13 |
| 2025/26 | 1.858 → 1.858 | .411 → .411 | 4.45 → 4.45 | .523 → .523 | 19.13 → 19.13 |
| 2024/25 | 1.763 → 1.763 | .428 → .428 | 4.22 → 4.22 | .557 → .557 | 19.01 → 19.01 |

Paired bootstrap (2,000 resamples over GWs, seed 1): captain, top-5 and positional picks each have difference
0.00, 95% CI [0.00, 0.00] in every season. Captain changes: 0/7, 0/35, 0/35. The 5-GW picks differences and
95% CIs are also 0.00 [0.00, 0.00] (3, 30 and 30 origins). Finished-week backtests are neutral as expected;
the targeted benefit is preventing live and partial-double data from changing team strength prematurely.

Regression coverage: live score changes versus pre-kick-off, partial and completed doubles, unaffected completed
teams in a live GW, missing/provisional flags, and raw versus already-filtered live rows. Fresh build validation
has zero errors (existing warnings: assumed GW8–9 targets and no GW11 match odds).

## 1 Nov 2026 — double-gameweek simulation seeds (PR #40); DGW under-projection found
- Bug (code review): fixture seed pid*1000 + g*10 + len(detail); detail[g] is set after the fixture loop, so both
  matches of a DGW shared one seed (identical start, rate and team-goal draws). Second fixture now has its own
  stream; first keeps its old seed, so single-fixture weeks are identical. dist only (sims are off in backtests).
- Check (scratch dgw_eval.py, sim 2000; DGWs 2025-26 GW26/33/36, 2024-25 GW24/25/32/33; 190 player-weeks each).
  Brier before -> after, paired bootstrap CI: p10 +0.0011 [-.0008,+.0034] / +0.0011 [-.0006,+.0032]; p6 -0.0043
  [-.0067,-.0021] / -0.0015 [-.0036,+.0007]; blank -0.0006 / +0.0020 (CIs wide). backtest --compare: nothing moved.
- Variant: same scoring-rate draw (sim_sigma q) in both matches: within 0.001 of independent. Dropped.
- Finding: DGW players under-projected, xP 4.64 vs 4.84 real (2025-26), 4.42 vs 4.98 (2024-25); p10 pred .12 vs
  real .16-.17; p6 .33 vs .35-.37. The old bug's over-dispersion partly hid the haul shortfall. Single-fixture weeks
  calibrated (2.28 vs 2.26, 2.06 vs 1.97). Next: diagnose by part (minutes rotation across two games? bonus?
  cal_int x nfx?) before the next DGW. Verdict on the fix: correct code, Marginal measured gain.

## 1 Nov 2026 — backtest hindsight in multi-week forecasts removed (PR #39)
- Code review finding: a forecast from GW k for k..k+4 (bench 5-GW totals, backtest.evaluate_horizons) read the
  injury flag saved at each TARGET week's deadline, and each later fixture's own odds (direct_w 0.85; archive
  pre-match or closing prices). The live odds file only ever holds the next round.
- Fix (backtest mode only, use_flags off): only the flag at the forecast deadline counts (later weeks: live
  no-return-date rule via availability_info); a fixture's own odds only for GW k (new param hist_odds_ahead = 0).
  Team ratings were already dated (market_ratings uses matches before k). Live projections unchanged.
- Bench (main 25d768f vs branch, archive odds): 1-GW identical on all three seasons (corr .434 / .411 / .428).
  5-GW corr .643 -> .604 (this season, 2 origins), .530 -> .523 (2025-26), .565 -> .557 (2024-25); 5-GW picks
  20.23 -> 18.27, 19.38 -> 19.13, 19.18 -> 19.01. backtest --compare (with and without status log): nothing moved.
- Read: past-season 5-GW levels were flattered ~0.008 corr / ~0.2 picks (odds only; archive has no flags). Earlier
  5-GW comparisons in this log had the leak on both sides, so variant differences stand; absolute 5-GW levels before
  1 Nov were too high. New 5-GW baseline: picks 18.27 / 19.13 / 19.01.
- Left: backtests zero players whose CURRENT status is 'u' in every past week (small 1-GW leak). Separate fix.

## 31 Oct 2026 — this-season evidence cap: `cred_recency` screened (local branch `cred-recency`, not adopted yet)
- Problem: player rates = (this season, weighted 0.8 per GW back) + w_last 600 + w_pos 450 pseudo-minutes. A run of
  full 90s converges to ~450 weighted minutes, so this season can never exceed ~30% of a rate however many games.
- Fix: new param cred_recency (None = old behaviour). `recency` still decides WHICH of this season's games count;
  cred_recency decides HOW MUCH this season counts against the priors (his minutes weighted by cred_recency per GW
  back). No minutes this season: priors only, as before.
- bench.py --no-h5 (baseline main 77f183a, archive odds), current model vs cred 0.85 / 0.9 / 0.95 / 1.0:
  corr current .434 -> .435 all; 2025-26 .411 -> .411/.411/.411/.410; 2024-25 .428 -> .429/.429/.430/.431.
  MAE moves <= 0.006 everywhere; picks within +-0.05, all CIs span 0.
  Captain: 2025-26 5.97 -> 6.00 / 6.43 / 6.63 / 6.60 (CIs +0.03 [0,+0.09], +0.46 [-0.31,+1.54], +0.66 [-0.26,+1.80],
  +0.63); 2024-25 9.34 -> 9.86 / 9.71 / 9.80 / 9.97 (+0.51 [0,+1.31], +0.37, +0.46, +0.63). Current (6 GWs) 8.50 ->
  8.50 / 8.50 / 7.00 / 7.00 (0.95+ change one captain of 6, -1.5).
  Captain changed in 2-3 / 5 / 7-9 / 8 of 35 weeks per past season. MID corr up slightly, GKP/FWD slightly down at 0.95+.
- Read: unlike the earlier global prior cuts (w_pos 250, recency 0.85: captain 6.69 -> 6.3), this change never lowers
  captain returns in past seasons, but the gain is small and not significant. Consistent with "player bias does not
  persist" (23 Oct): the cap is real but rarely changes who ranks top. 0.85 = safest (CI lower bound 0 both seasons).
- Not yet run: backtest.py segments with and without the status log, bench 5-GW totals. Verdict so far: Marginal.

## 31 Oct 2026 — three-way follow-up: late-selling xMins (PR #29), display parts (PR #28), archive-odds re-tests (rejected)
Bench baseline on main 34b3910 with archive odds: current corr .434 / rank .549 / picks 4.14 / cap 8.50; 2025-26 .411 /
.509 / 4.45 / 5.97; 2024-25 .428 / .512 / 4.22 / 9.34. 5-GW picks 20.23 (2 origins) / 19.38 / 19.18.
- PR #29 `model-xmins-selling` (param xmins_sell, OFF; shadow logged each build). xMins retrained on 2022-23 + 2023-24
  with sell_share, sell_spike, log_own (B) vs same 21 features (A) vs shipped (S). Start Brier, played-in-last-3, test
  2024-25 .1464 / .1477 / .1420 (B-A -.0057 [-.0073, -.0041]); 2025-26 .1443 / .1451 / .1379 (-.0072). Likely starters
  with 8%+ selling .223 -> .179 and .221 -> .177; xMin bias +13.4 -> +1.8. Next GW only. Bench on vs off: corr +.007 /
  +.015 / +.012, rank +.009 / +.022 / +.020, 1-GW picks +0.14 [+.02,+.30] / +0.09 / +0.05; 5-GW picks 2025-26 +0.13
  [-.00,+.29], 2024-25 +0.11 [-.03,+.25], current -0.09 (2 origins). --compare: top 30 MAE +0.08/+0.09 this season
  (2025-26 -0.07 [CI excl. 0], 2024-25 +0.02); start Brier worse GW3-5 and with 1-2 games of history. Live inputs:
  element-summary per window (669 calls, ~2/week, cached history/sell_hist.json) + bootstrap open-window balance;
  last pre-deadline snapshot has ~96% of final transfers. Verdict: Marginal; switch on after ~6 GWs if
  tools/score_shadow.py shows lower shadow start Brier (CI < 0) and no worse xP MAE.
- PR #28 `model-display-parts`. DC count in 60+ games negative binomial r=5 (DEF/MID/FWD) instead of Poisson;
  dc_blend 4 -> 8; assist_pos FWD x1.8; bonus_scale 0.8 -> 0.95; cal_slope/cal_int 0.86/0.33 -> 0.96/0.00 (LS fit, bench
  window). Bug found: archive._priors gave every player a last-season DC rate of 0 in 2025/26 (seasons before had no
  DC) — most of the audit's 2025/26 DC shortfall; live priors.json unaffected. Shown DC 2025/26 .122 -> .183 vs .200
  real; DC bands calibrated. Totals: corr +.002/+.001/+.003, picks CIs none below 0, 2025/26 top-5 +0.29 [+.01,+.57],
  bias toward 0 (MAE 2025/26 +0.008 is the bias removal). Tripped: this season's top 30 bias +0.02 -> +0.27 (past
  seasons move toward 0: -0.43 -> -0.13, -0.37 -> -0.17); £7.0-9.9m MAE +0.045 (bias toward 0). Verdict: Marginal.
- Archive-odds re-tests (no PR). (A) Fixture-difficulty H / fdr_cs 0.3: past-season hard-fixture CS over-prediction
  still exists with odds (2025-26 FDR 4-5 .197 pred vs .115 real) but FDR 3 is over too (.301 vs .249; .284 vs .232),
  so it's a past-season CS level issue, not an FDR one; live FDR 4-5 calibrated (.203 vs .212) and H over-corrects
  (.111). Corr/rank flat, goals-conceded and saves corr worse, live 5-GW picks H -0.82 [-1.42,-0.22]. Reject. Lead:
  past-season cs_k level check. (B) team_recency 0.95-0.97: with odds, team ratings barely matter; 2024-25 5-GW
  +0.02-0.04, 2025-26 -0.04 to 0. Reject. (C) Planner decay replay (8 start x season pairs, 840 solves): vs 0.9, 0.8
  -13.1 pts/season [-53.6,+22.1], 0.75 -39.6 [-95.8,+19.9], fewer hits but no more points. Keep 0.9. (D) recency 0.9
  for GW2+ of the horizon: 5-GW picks +0.00 / +0.06, CIs cross 0. Reject.

## 30 Oct 2026 — adopted: xMins minutes model on by default (PR #23, commit `0468850`)
(Entry added 11 Nov 2026 from `docs/xmins-eval.md` and the comment on `DEFAULTS["xmins"]` in fplmodel.py; no new runs.)
- What: start chance and minutes come from the external XGBoost model in `xmins.py` (four models, trained on 2022-23
  and 2023-24, stored as plain JSON in `xmins/`) instead of the weighted counts. Availability, Europe and the return
  ramp still apply on top. `xmins_combine` "B" (bench chance unconditional, capped at 1 − start chance): A had lower
  MAE but −0.1 to −0.2 points bias.
- Minutes, players who played in the last 3 GWs, counts → xMins (2026/27 GW3-8 with status log / 2025-26 / 2024-25):
  start Brier 0.148 → 0.121 / 0.182 → 0.145 / 0.184 → 0.149; 60+ Brier 0.156 → 0.137 / 0.182 → 0.157 /
  0.187 → 0.163; xMin RMSE 27.7 → 26.5 / 31.0 → 29.3 / 31.4 → 29.6. xMin MAE got worse (16.9 → 19.2 / 20.5 → 22.3 /
  21.0 → 22.6): MAE rewards all-or-nothing guesses.
- Points (bench.py): corr 0.429 → 0.434 / 0.387 → 0.403 / 0.412 → 0.426; MAE 1.806 → 1.796 / 1.887 → 1.867 /
  1.780 → 1.770. Top-N picks unchanged; captain within noise except 2024-25 +0.60 (CI +0.09 to +1.37).
- `--compare` flag, with the status log: top 30 projected, bias −0.27 and MAE +0.04 (base top-30 bias was +0.25, so
  mostly a correction; top-30 corr fell 0.02).
- Not covered: new signings still get about 0.05 start chance; players who played this week after missing the
  previous 3 got worse (start Brier 0.21 → 0.26, n=128); domestic cup rotation.
- Missing input: model files missing or xgboost not installed → `project()` raises; validate.py fails the build if
  xMins is on but a player with a next-GW fixture fell back to the counts. Full write-up: [xmins-eval.md](xmins-eval.md).

## 29 Oct 2026 — bonus fixture-response params: rejected (branch `model-bonus-fixture`)
- New params (defaults = current): bonus_att_pow (0.5), bonus_own_pow (0), bonus_def_pow (0.3); also bonus_scale.
- Three-season bench: no variant changes corr/rank at 3 dp. att 0.8/1.0: picks ~0, top-5 mixed (1.0: 2026/27 -0.40,
  CI excludes 0). own 0.2/0.4: nil or slightly negative. att 0.8 + own 0.4 + scale 1.0: 2026/27 picks +0.06 but
  2025/26 picks -0.05 (CI excludes 0). bonus_def_pow 0.6/1.0: nothing consistent.
- Diagnostic (2025/26): real bonus easy/hard ratio ~1.9x MID/FWD, ~2.4x DEF/GKP; model ~1.15x. Steeper attack exponent
  moves MID/FWD to ~1.28x only. bonus_own_pow goes the WRONG way for defenders (easy-fixture clean sheets outweigh
  teammates' goals taking bonus). Top-30 projected bonus 0.32 vs actual 0.42 (level, not ranking).
- Conclusion: bonus fixture shape is wrong but fixing it doesn't change who the model ranks highly. Don't retry
  bonus re-shaping unless the structure changes (consistent with per-part calibration result, 22 Oct).
- Note: the 2026/27 bench baseline has moved to corr 0.430 / rank 0.540 / picks 4.18 / cap 7.17 on latest main
  (status log has grown since 28 Oct). Use the current printout as the reference, not the older figures.

## 29 Oct 2026 — planner discount replay and "bonus as a contest" data check: no change adopted
- Planner decay (optimise.solve, default 0.9 per week; plan horizon 5 GWs). Season replay, balanced strategy, no
  chips/flags, GW4-38, 4 start squads x 2 seasons, decay 0.75-1.0. Reproduces 2025/26 balanced 1,868 at 0.9.
  Start-squad swings of +-100-160 pts dominate; best decay differs by season and start. Two-season mean of start
  means: 0.75 2,030; 0.95 1,987; 0.8/0.85 1,985; 1.0 1,982; 0.9 1,967 (spread within noise). Pooled CI excludes 0
  only for 0.75/0.8 in 2024/25 (+87/+68 per start); 2025/26 0.75 +38 (CI -16 to +89). Lower decay = fewer hits
  (0.75: ~5.5/season vs 1.0: ~13.5). Per-player uncertainty fade (xP x p_start^(w*gamma)): single-start, inconsistent.
  Verdict: keep 0.9 (Coin flip). If revisited: 0.75 on more starts and 2023/24.
- Bonus as a contest (data only, 2023/24-2025/26, 1,140 matches): bonus = top-3 BPS in 99.8% of matches, pot ~6.4.
  Strong realised contest effect (1 goal: ~2.2 bonus with no other scorers vs ~1.0 with 3+; DEF/GK hurt by own
  team's goals). Pre-match size small: elite striker +0.27 (easy) / -0.13 (hard) per match vs flat rate; MID/DEF
  < 0.15. Implied bonus elasticity to team attack ~0.8 vs model's 0.5. Non-event BPS/90 persists 0.6-0.65
  season to season (bonus/90 0.3-0.5). Haaland 3-season bonus 1.07/90 (the 1.74 above was a small 2026/27
  sample); per-goal bonus normal, gap is goal frequency. Verdict: whole-match BPS simulator not worth it (Marginal).
  Cheap candidates to bench: bonus fixture exponent MID/FWD 0.5 -> ~0.8; DEF/GK bonus falling with own team's
  expected goals; re-tune bonus_scale.

## 29 Oct 2026 — absence-adjusted team strength, perfect-hindsight check: rejected (branch `model-absence-adj`)
- Idea: adjust opponents' attack, opponents' defence and own defence (GK + DEF) for who is missing, using the share of
  the team's recent xG+xA (attack) or GK/DEF minutes (defence) of players who actually played 0 mins (oracle, centred
  on the league mean each week). Own attack not adjusted (teammates' shares would rise; can't redistribute).
- Ceiling is ~zero: pooled RMSE 1-6 GWs ahead -0.1% (2024/25), -0.05% (2025/26); attack unchanged; defence -0.004 to
  -0.007 but partly a leak (a missing defender lowers his own CS projection). Leak-free variants ~0. 5-week totals:
  corr +0.003/+0.005, picks within CIs. 2026/27 -0.6% RMSE over 6 origins, CI spans 0.
- Why: Poisson elasticity of goals to line-up presence ~0.12-0.30, so a big absence moves expected goals only a few
  percent. Only 25-35% of big absences are multi-week (knowable in advance); the rest look like rotation.
- Lesson: first-version normalisation on the in-sample window was biased (mean att 0.91, def 1.10) and flattered
  results; centre per week. Re-test only if 2026/27 shows a gain over ~30 GWs.

## 29 Oct 2026 — crowd selling as a team-news signal (archive test; live logging PR #18)
- Signal: net transfers out before the deadline as a share of ownership (sell_share), or that minus the player's own
  6-GW median (sell_spike). Archive transfers for GW k are pre-deadline (GW1 balance is 0 in both seasons).
- Likely starters (model p_start >= 0.8): start rate with 8%+ selling 0.641 (n 702, 2024/25) and 0.622 (n 617,
  2025/26) vs 0.892 with no selling; model predicts ~0.98 for both. Points gap -0.61 / -1.05 per player-week.
  Holds after a decent previous match (0.67 / 0.65), so it is news, not form-chasing. Players with 80+ mins in both
  previous matches and 8%+ selling still start only 76-77% vs 91-92%.
- Injury control (0 mins in previous match) removes almost no rows, so it can't measure how much is public injury
  news the live model already sees through flags. The archive has no flags: it very likely overstates the gain.
- Projection test, fitted on the other season: corr +0.005 to +0.009, rank +0.009, MAE -0.07 to -0.09; picks,
  captain and top-5 CIs all span 0. Simple rule (sell_spike > 8%, xP x ~0.65) gets most of it.
- Verdict: research only. Real test on live data: history/transfers_gw*.json (PR #18) + history/status.json,
  only players with no flag at the deadline, after ~5-6 GWs. First candidate: sell_spike > 8% -> x0.65.

## 28 Oct 2026 — fixture difficulty and cross-season player prior, three-season bench: neither adopted
Bench now covers 2026/27 (GW3-8, with odds), 2025/26 and 2024/25 (GW4-38, no odds). Baselines: corr / rank / picks / cap
0.420 / 0.522 / 4.09 / 7.17; 0.387 / 0.484 / 4.34 / 6.69; 0.412 / 0.498 / 4.30 / 8.54.
- Fixture difficulty (branch `model-fixture-cs`, params off: fdr_cs, fdr_att, cs_curve; rebuilt candidate H).
  Key finding: live hard-fixture clean sheets are already calibrated (FDR 4-5 team CS pred 0.203 vs actual 0.212,
  33 team-games; verified independently). The 0.24 vs 0.12 gap only exists in the odds-free archive seasons, where
  CS is also over-predicted at FDR 3 (0.30 vs 0.25), so it is a missing-odds level error, not a fixture-shape one.
  Likely starters FDR 4-5 residual: 2026/27 -0.34, 2025/26 -0.63, 2024/25 -0.48 (not a CS problem live).
  H (fdr_cs 0.3 + fdr_att 0.1): corr +0.002/+0.005/+0.004, picks +0.09/+0.02/-0.01 (all CIs span 0), captain
  2025/26 -0.43 (CI to 0.00); over-corrects live CS at FDR 4-5 to 0.11. fdr_cs alone similar. fdr_att alone: nil.
  Fitted CS curve sigmoid(a + b ln mu_a + c (fdr-3)), fit on another season: top-5 CI negative on 2026/27
  (-0.17) and 2025/26 (-0.20); fits disagree. FDR coefficient negative in every fit (-0.29, -0.42).
  Verdict: research only. Revisit after backfilling odds into archive seasons.
- Cross-season player residual prior (branch `model-player-prior`, params off: resid_w, resid_k, resid_bonus_only;
  player_prior.py). Persistence of per-player (actual - projected), regulars: 0.40 (2023/24 -> 2024/25), 0.13
  (2024/25 -> 2025/26); bonus-only 0.26 / -0.02. Top-10 residuals shrink from +1.75 to ~+0.35 next season.
  Haaland residual +2.02, -0.28, +1.55 by season: not predictable. Best variant (k 40, w 0.5): 2025/26 picks
  -0.03, captain -0.46; 2024/25 corr +0.007. Verdict: reject.
- Next: backfill football-data.co.uk odds for 2024/25 and 2025/26 into archive.py (blocked in the Claude sandbox,
  works from GitHub Actions; odds.py already has the parsing and lambda fit). Without it, archive tests judge an
  odds-free model, which is not the live one.

## 28 Oct 2026 — OpenFPL paper (Groos 2025, arXiv 2508.09992) compared and tested: nothing adopted
- Paper: XGBoost + Random Forest per position, 1/3/5/10/38-match means of FPL + Understat stats (ICT,
  BPS, xGChain, PPDA...), points as target, band-balanced sample weights, median of 50 models; trained
  2020/21-2023/24, tested 2024/25 GW32-38 against FPL Review. Scripts: scratchpad paper_eval.py and
  stack_test.py (not in repo). 2024/25 archive loads once element_type 5 (assistant managers) is dropped.
- FPL Lab on the paper's window (2024/25 GW32-38, no flags), RMSE by band zero/blank/ticker/haul, change
  vs Last 5: 1 GW ahead -8.0/-15.6/-24.7/-7.5% (FPL Review -12.9/-15.1/-25.4/-7.9; OpenFPL
  +3.4/-7.8/-29.0/-8.4). 2 GW: -10.4/-16.8/-24.9/-7.8. 3 GW: -8.3/-16.5/-14.6/-6.9. Absolute: 0.715 /
  1.519 / 1.387 / 5.469. The paper's Last-5 zero band reproduces (0.786 vs 0.791) but blanks/tickers
  don't (1.83 vs 1.40 / 2.14), so compare relative gains, not raw band RMSE.
- Trees trained on 2023/24-2024/25, tested 2025/26 GW6-38 (bench metrics; current model corr 0.386, rank
  0.483, picks 4.32, cap 6.55, top-5 5.36):
  OpenFPL-style trees: corr 0.364, picks 3.93 (CI -0.56 to -0.23), top-5 -0.86 (CI -1.68 to -0.07).
  With band weights: haul RMSE 5.82 -> 4.70 but zero 0.70 -> 1.27, blank 1.46 -> 2.54, picks 3.85. The
  paper's haul edge is a weighting trade-off, not extra skill; don't optimise haul RMSE.
  Stacked (trees + FPL Lab parts) / residual: corr 0.394-0.396, RMSE 1.933 -> 1.921, picks -0.07/-0.09
  (CI spans 0), top-5 -0.62/-0.65 (borderline). Blend 0.75 FPL Lab + 0.25 stacked: picks +0.05 (CI
  -0.03 to +0.13), top-5 -0.42 (CI -0.87 to -0.01). Trees compress the top end.
  Residual feature importance is flat (no feature above 2.5% of gain): no missing signal in ICT, BPS,
  shots or long windows.
- Median of 9 parameter variants (recency 0.7/0.85 x min_recency 0.3/0.5 x w_pos 350/550 + defaults):
  identical to the current model on both seasons (captain unchanged in 41/41 weeks).
- Takeaways kept: add 2024/25 to bench.py (third season); report 2 and 3 GW-ahead accuracy (the solver
  plans 6 GWs; zero-band error grows ~22% by 3 GWs); Model tab should show gain vs Last 5 rather than
  ticks against FPL Review's raw band RMSE. The paper agrees the commercial edge is minutes/team news
  (zeros and blanks), which matches this log's conclusion.

## 23 Oct 2026 — honest backtests (PR #11) and fixture difficulty research (not adopted yet)
- PR #11: backtest flags read only the status log saved at each deadline (ctx["out_log"]); no more
  hindsight flags from today's notes, and the cleared-news rule no longer zeroes players in backtests.
  Honest 2026/27 baseline: corr 0.424, rank 0.528, picks 4.09 (was 0.438 / 0.553 / 4.20). 2025/26
  unchanged (0.387 / 0.484 / 4.34). Live projections unchanged. bench.py comparisons now print a paired
  bootstrap 95% CI for captain, top-5 and picks; quote it before rejecting on captain.
- Possible leak left: use_out (minutes history skips hindsight injury weeks). Off: 2026/27 corr 0.424 ->
  0.428. Re-test when the status log covers more weeks.
- Fixture under-reaction, diagnosed (likely starters, hard FDR 4-5 minus easy 1-2): model spread -0.79 /
  -0.56 vs actual -1.42 / -1.45 (26/27 / 25/26). Biggest part: clean sheets in hard fixtures
  over-predicted (25/26 team CS rate 0.24 predicted vs 0.12 actual; easy end fine). Bonus is flat vs
  fixture (pred -0.04 vs act -0.16/-0.20). 2025/26 attack spread too narrow without market odds.
  cal_slope explains only 10-21%; opp_adj 0 changes nothing. Team-CS likelihood prefers an FDR term
  (about +0.17 on mu_a) over a power curve.
- Candidates, honest bench (hist_flags off), best = H: hard fixtures only, mu_a x exp(0.3 x (FDR-3)),
  attack and bonus x exp(-0.1 x (FDR-3)) for FDR > 3. 26/27 corr 0.424 -> 0.427, picks 4.09 -> 4.26;
  25/26 corr 0.387 -> 0.392, rank 0.484 -> 0.488, picks 4.34 -> 4.36; hard-end residual +0.48 -> +0.07
  / +0.63 -> +0.22. Captain 25/26 -0.43, CI -1.23 to 0.00 (two GWs; borderline). Symmetric versions
  (fdr_cs 0.25) push easy-fixture defenders to the top of the captain list (16 of 35 GWs) and fail.
  fdr_att 0.10 alone fails on captain (CI -2.00 to -0.20). Verdict: Marginal; code in the research
  worktree (tests/fixtures_research/), not merged.

## 23 Oct 2026 — stress test (branch `stress-test`, tests only; `tests/stress/REPORT.md`)
- CRITICAL, live only: build.py feeds the in-progress GW's live data into the model. Players yet to play
  show 0 minutes that week, so start chance drops to 0.39 (min_recency 0.4). Local build mid-GW8:
  Haaland GW9 5.00 -> 1.96, Palmer 4.25 -> 1.67; top-100 -1.97 xP. Backtests can't see it. Fix: drop
  live rows for clubs whose GW fixture hasn't finished (tested in mid_gw.py: identical to clean data).
- Leaks in the 2026/27 bench: (a) past injury flags are rebuilt from today's FPL notes, and only notes
  that proved right survive (62/62 flagged pool rows really played 0 mins). hist_flags off: corr 0.438
  -> 0.424, rank 0.553 -> 0.528, picks 4.20 -> 4.09, so up to 0.014 corr is hindsight. (b) news_absences
  feeds ctx["out"], which the backtest's flag rule reads: Gravenberch/Gibbs-White GW7 projected 0.00
  instead of 2.18/3.46 (corr -0.001). The earlier "unchanged" check toggled news_abs, which doesn't reach
  this path. 2025/26 is unaffected (no flags in the archive). Use history/status.json once it covers
  the test weeks.
- No measurable leak: DC thresholds as of each GW (FWD threshold is learned as 16 from one data point;
  the rule is 12), current-club xG (10 rows), odds (football-data pre-closing averages, Fri/Tue).
  Calibration refit on 2025/26 only is slightly worse on 2026/27, so tuning on GW3-7 isn't flattering it.
- Bench noise: pen_xg 0.05 -> 0 changes the captain in 7/35 weeks of 2025/26; cap Δ -0.63, 95% CI -1.69
  to +0.23. Median gap between the top two projections 0.21 pts. Several "captain 6.69 -> 6.x" rejections
  above were inside this noise. Decide on corr, rank and picks; quote a paired bootstrap CI for captain.
- Fixture difficulty: likely starters (p_start >= 0.8) are over-projected +0.53 to +0.73 in FDR 4-5 and
  under-projected -0.3 to -0.7 in FDR 1-2, every position, both seasons (one exception). Team ratings
  ** 1.25 / 1.5 don't fix it (2025/26 corr +0.002, captain -0.94, CI -1.97 to -0.17). Next: FPL FDR as
  an input, or separate attack/CS fixture exponents.
- Sensitivity ±20% on every DEFAULTS param: most fragile home x0.8 (2025/26 corr -0.016), cs_k (up to
  -0.005); all others within ±0.002.
- Players: no persistent per-player or archetype bias (split-half corr 0.04). Cheap players (< £4.5)
  -0.26 ± 0.04 (25/26), -0.13 ± 0.12 (26/27), but priced with hindsight: Marginal.
- Optimiser: FPL FT rules correct (solver and ftTable). Problems: optimise.py accepts CBC "Not Solved"
  and timed-out incumbents without saying so (budget-breaking plan at <=0.2 s; production solves 0.6-3
  s); browser HiGHS aborts on 2/12 real inputs (fixed by mip_rel_gap 0.01 or another seed); locks
  outside the candidate pool are dropped silently; capPick's 0.6 swap changes the captain in 18/80 plan
  weeks; bestXI ignores the Safe/Chase terms (Safe XI differs in 39/80 weeks).
- Decision replay 2025/26 GW4-38 (same GW4 squad, no chips, no flags): Template 1,993, Chase 1,889,
  Safe 1,872, Balanced 1,868, Always roll 1,791, Form 1,729. No difference vs Balanced is significant
  (template +125, CI -80 to +313); template likely benefits from ownership knowing injury news, which
  the archive model lacks. Re-run on 2026/27 when the status log has enough weeks.
- FPL ep_next comparison: no finished-GW snapshot yet (first is GW8).

## 23 Oct 2026 — 10 random players (2025/26) + four targeted fixes: none adopted
- 10 regulars (seed 2026, 20+ appearances, GW4-38), mean gap actual - projected: Yarmoliuk -0.05,
  Doku +1.20, Mosquera -0.53, Chukwueze +0.16, Ajer +0.11, Barry +0.13, Vicario -0.93, Willock -0.17,
  Richarlison +0.48, Sessegnon +0.35. 7 of 10 within ±0.5; per-player MAE 1.27-2.94 is mostly match noise.
- Player bias does not persist: split-half (GW4-20 vs GW21-38) residual corr 0.016 over 270 regulars;
  goals minus xG persistence -0.04 (MID/FWD). So no per-player residual correction. Bonus/90 does
  persist (0.24).
- Team defence looks over-shrunk in hindsight (DEF+GKP bias MCI +0.77, ARS +0.53, BUR -0.59, WOL -0.38).
- Start-chance bands (2025/26, no flags): p_start 0.8-0.95 pred 3.10 vs act 2.74; 0.95+ 3.53 vs 3.34;
  under 0.5 1.04 vs 1.33. Same over-confidence as noted in diagnosis.
- Tested on bench.py (local switches, reverted): bonus-only shrink w_pos_bonus 150/50 (neutral; current
  top-5 5.48 -> 4.92-5.00); team prior_games 2/1, team_recency 0.97, def_pow 1.2/1.4, att+def pow 1.2
  (corr +0.001-0.002, DEF corr 0.368 -> 0.371, but 2025/26 captain 6.69 -> 5.57-6.40); less position
  shrink for established players (2000-2500+ prior mins, cut 50-100%: corr +0.002, captain 6.69 -> 5.46-6.06).
- Conclusion unchanged: reshaping the same data doesn't help. Next gains need new inputs (player odds,
  predicted line-ups) and a live log of rival projections to learn from.

## 23 Oct 2026 — checked, no change: Haaland under-projection (models disagree on GW8)
- GW8 Haaland: FPL Lab 4.71, FPL Review 5.7, Fantasy Football Pundit 6.4, FPL ep_next 9.5 (form only).
  Breakdown (calibrated): minutes 1.64, goals 1.89, assists 0.22, bonus 0.70. Model xG/90 0.72 vs his
  real 0.83 this season and 0.76 last; bonus/90 real 1.74 vs ~0.9 in the model; xmin 82 (UCL Wed).
- Backtest, Haaland only: 2026/27 GW3-7 pred 5.54 vs actual 8.60 (5 GWs); 2025/26 GW4-38 pred 4.96 vs
  6.52 (33 GWs). About 1.6 pts/GW short over 38 GWs.
- It is a Haaland effect, not a top-end one: top-5 by projection pred 5.23 vs act 5.45-5.48 both seasons;
  2025/26 pred 6+ 7.41 vs 7.39. "Elite FWD" (model xG/90 >= 0.6) is ~90% Haaland rows.
- Global fixes tested on bench.py, none adopted: w_pos 250/150 (captain picks 2025/26 6.69 -> 6.29-6.31),
  w_last 1200 (captain 6.69 -> 4.89), w_last 1500 + w_pos 250 (5.14), recency 0.85 (6.60). Corr flat.
- Decision impact is small: he is already the model's top captain pick most weeks (3 of 5 this season),
  so the under-projection mainly understates his value in the solver, squad rating and EO "swing".
- Next test if revisited: a player-level residual prior (points vs projection over the previous season,
  heavily shrunk) — needs the 2024/25 archive to test on 2025/26 without leakage.

## 23 Oct 2026 — adopted: cleared-news absences (`news_absences` in fplmodel.py)
- Problem: Gibbs-White started GW1-6 (90 mins each), missed GW7 with no flag showing afterwards; FPL's
  last news change was 16 Oct, the day before the GW7 deadline. The status log only began on 22 Oct, so
  the model read GW7 as being dropped: start chance 39%, xP 1.8.
- Rule: a player now available, who missed his club's latest finished game with 0 minutes, had started
  2+ of the 3 club games before it, and whose FPL `news_added` is no earlier than 7 days before that
  deadline, counts as out that week (skipped in minutes history; return ramp x0.6 then x0.7 applies).
- Only the latest finished GW, so earlier backtests are unchanged (GW3-7 corr 0.438 before and after).
  Can't be tested on past seasons (no news history). Check on GW8 results: affected players were
  Gibbs-White (xP 1.8 -> 3.2) and Gravenberch (0.9 -> 1.8).
- Also: `xmin` now equals the minutes the projection uses next GW (after flags, Europe rotation and the
  return ramp); the old figure is `xmin_base`, still used for the "selectable" check.

## 23 Oct 2026 — strategy terms in the optimiser (planning, not projections)
- Chase rank: `haul_w` x chance of 10+ points (simulated `dist` p10) per starter, double for captain.
  Play safe: `hit_margin` (a hit must gain 4 + 2) and `nail_w` (marks down starters by 1 - nailed/100).
  Tested on the GW8-12 plan (4 FTs): Chase haul_w 3 changed nothing; 10 gave haul chance +9% at ~0 xP
  cost; Play safe cost ~2.7 xP over 5 GWs for a more template XI (top-10k EO 0.58 vs 0.50). With 1 FT no
  strategy took a hit: none of the available upside is worth a -4. Settings: STRATEGY in build.py and
  STRAT in site/js/core/model.js (keep them equal).
  (Since moved: STRATEGY is in optimise.py. Note added 11 Nov 2026.)

## 22 Oct 2026 — merged (PR #2)
- Two-season test bench (`bench.py`, `archive.py`).
- Minutes skip blank gameweeks and weeks before a player joined; minutes recency 0.4; player-rate recency 0.8.
  2025/26: corr 0.372 -> 0.387, rank 0.459 -> 0.484, RMSE 2.767 -> 2.750.
- Injured vs dropped: status log (`history/status.json`), injured weeks skipped in minutes history,
  return ramp (start chance x0.6 then x0.7), return dates parsed from FPL news, "Unknown return date"
  returns over 6 GWs. Simulated-injury test on 2025/26: corr 0.421 -> 0.424, top-5 picks 5.49 -> 5.62.
  Re-test on real records once the status log has several weeks.

## 22 Oct 2026 — opened (PR #3): simulated outcomes
- Monte Carlo per fixture (4,000 runs): starts/sub/none, team goals for and against, goal and assist
  shares by thinning, CS, GC, saves, DC, bonus (allocated to players with returns), cards, lognormal
  uncertainty on scoring rate (sim_sigma 0.5). Each player's runs are shifted by whole points so the
  average equals xP.
- Chance error (10+, 6+, 2-or-fewer; Brier, lower is better): 2025/26 GW22-38 0.1105 vs 0.1200 for a
  normal curve on optimise.variance, 0.1225 with no model; 2026/27 GW3-7 0.1110 vs 0.1176 vs 0.1254.
- The variance formula still fits the size of misses better (it was fitted on residuals), so Play safe
  / Chase rank keep it. Lessons: don't apply the xP calibration to individual simulated scores
  (turns 2-pointers into 2.05); simulated spreads are narrower than reality, mainly from minutes.
- Shown in the app: player sheet "GW outcomes" tiles; haul chance for C and V in the captain check.

## 22 Oct 2026 — tested, not adopted
- Penalty-taker bonus (pen_xg 0 to 0.15): no clear effect.
- Longer minutes window (6-8 GWs): worse.
- Flat squeeze of start probability (e.g. 0.08 + 0.82p): tiny gain last season, slight loss this season.
- Per-part calibration (separate multipliers for goals, assists, CS, bonus, etc. per position; ridge
  regression or ratio-to-real): small corr gains at best, and top-5 picks worse on both seasons.
  Reason: the total score is already calibrated in every projection band; attacking points are
  under-counted but appearance points are over-counted by about the same amount. Boosting attack
  inflates the top players. Don't retry unless the structure of the model changes.
- Share-of-team-xG model (player's share of team xG while on the pitch x the team's expected xG,
  shrunk to the existing rate; prior weight 2-1000 team-xG, share memory 0.8-0.97): corr +0.001 at
  best, rank and top-5 picks slightly worse last season. Reason: the model already scales each
  player's rate by his team's (market-blended) attack rating and adjusts for opponents, so shares
  add no new information.
- Blending FPL-style form (points per GW over the last 4) into xP (`tune_ep.py`, GW3-7 2026/27):
  worse at every weight. w 0.05 corr 0.4165 vs 0.4169; w 0.2 0.409; form alone 0.308. FPL's real ep
  is now snapshotted each GW in `history/proj_gw*.json`; re-test with real ep after ~4 GWs.
- Club substitution patterns for minutes (params `p60_prior`, `mstart_prior`: shrink a player's
  chance of 60+ when starting, and minutes when starting, towards his club's same-position rate;
  2-20 pseudo-starts): worse on both seasons at every weight (2025/26 corr 0.387 -> 0.380-0.385,
  top-5 and captain picks down). His own history already captures it.
- Last season's start rate as a prior on start chance (`start_prior`, rate = minutes / 3230):
  0.5 pseudo-games gives corr 0.387 -> 0.392 (2025/26) and 0.437 -> 0.440 (current), but captain
  picks 6.69 -> 5.40 and top-5 5.45 -> 5.18 last season, and projections drift low (bias -0.09).
  Larger weights are worse everywhere. Not adopted; params left in the model at 0 (off).

## Where the error comes from (Model tab "Biggest misses", added 22 Oct 2026)
Each recent GW re-projected from data before it; the absolute gap per scoring part, shared out.
GW4-7 2026/27: Defence (CS, goals conceded, saves, DC) 31-38%, Attack (goals, assists) 31-37%,
Minutes 14-17%, Bonus 9-10%, Cards and other 6-8%. Average miss 1.76-1.89 pts per player.
Defence and attack misses are mostly match luck; minutes is the share better team news could cut.

## Diagnosis notes (2025/26)
- High projections (5-7 xP) are well calibrated.
- Start probability is over-confident: "certain" starters start ~86% (backtest without flags).
- Fringe players are slightly under-projected (they play more than expected); matters little for picks.
- Bonus is under-counted ~25% at population level but, as above, the total is calibrated.

## Conclusion so far
Re-shaping the same FPL xG and minutes data has hit diminishing returns (confirmed again for minutes
on 22 Oct). Further gains need new information:
- injury status history (collecting since 22 Oct 2026; re-test the injured-vs-dropped logic in a few weeks);
- player-level betting odds (anytime scorer / assist), which price in team news and pens;
- expected line-ups (press-conference news) for the minutes model;
- FPL news history (`history/news.json`, collecting since 22 Oct 2026): when flags appear and change.

## Player odds providers (researched 22 Oct 2026; check before buying)
- The Odds API: free 500 credits/month; paid from $30/month (20K credits). EPL player props not
  confirmed on their EPL page (example shows shots on target; props "mainly US bookmakers"). Test
  with a free key first. ~10 fixtures x 2 markets per refresh.
- SportsGameOdds: EPL anytime goalscorer (Yes/No) and assists (O/U) confirmed, 20+ books. EPL is not
  in the free tier; Rookie $99/month.
- Betfair Exchange API: delayed key free (for development use; 1-180 s delay); live key one-off fee
  (Betfair help page says £499; older guides £299). Needs a KYC-verified account. Exchange prices
  have no bookmaker margin, but goalscorer-market liquidity is unchecked.
- odds-api.io: from £49/month; soccer props not confirmed.
- Sportmonks: base plans €29+/month plus odds add-on (premium odds from €129/month); player markets not confirmed.
- Historical player odds need paid tiers everywhere, so plan to collect odds for a few weeks before
  testing them in the model.

## Other candidates
- Prior for new signings / players with no history.
- Past-season clean-sheet level (cs_k) with odds: CS over-predicted at FDR 3 and 4-5 in 2024/25 and 2025/26 (31 Oct).
- Backtest leak: current status 'u' zeroes a player in every past week (1 Nov). Use status at the time.
- Double-GW under-projection: xP ~0.2-0.6 low, haul chance ~5 points of % low in past DGWs (1 Nov).
