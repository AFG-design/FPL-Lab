# FPL Lab stress test — 23 Oct 2026

Tests only: nothing in `fplmodel.py`, `optimise.py`, `build.py` or `site/` was changed. Every script here runs from the repo root data (`python3 tests/stress/fetch_raw.py` first to write `raw/`). Bench baseline matches the model log: 2026/27 GW3-7 corr 0.438, 2025/26 GW4-38 corr 0.387, captain 6.69.

Severity follows the brief: **Critical** = leakage or wrong FPL rules. Where a Critical has tiny measured impact, the evidence column says so.

## Findings

| # | Area | Severity | Evidence | Decision impact | Suggested fix | Confidence |
|---|---|---|---|---|---|---|
| 1 | Live build: in-progress GW | **Critical** | `build.py` feeds the current GW's live data into the model. Players whose match hasn't kicked off show 0 minutes, so start chance drops to 0.39. Real local build tonight (GW8, 1 game played): Haaland GW9 5.00 → 1.96, Palmer 4.25 → 1.67, Raya 3.56 → 1.33; top-100 players −1.97 xP; no-transfer plan GW9 ≈22 xP. Invisible to backtests (finished GWs only). `mid_gw.py` | Yes: every projection, plan, captain and XI is wrong from each deadline until the GW ends | In `build.py`, drop live rows for clubs whose GW fixture isn't finished (`drop_unplayed` in `mid_gw.py`): max difference from the clean projection 0.00 | Strong |
| 2 | Optimiser: time-limit results | **Critical** (rare) | `optimise.py` accepts CBC "Not Solved". At ≤0.2 s it returned a plan with bank −£1.1m on replay and 311 "xP" vs 254 optimal. At 1 s pulp says "Optimal" at 251.5 vs 254.2 with a phantom hit. Production solves take 0.6-3 s of a 40 s limit | Not today; would if the Actions runner is slow | Return None unless `sol_status == 1`; legality-check every plan; add status and gap to the result | Strong |
| 3 | Browser Re-plan (HiGHS) | High | Aborts (`RuntimeError: Aborted()`) on 2 of 12 real inputs (chase FT2, safe FT5), reproduced in Node with the shipped build. `mip_rel_gap` 0.01 or `random_seed` 7 solves the same model. Also accepts "Time limit reached": at 0.02 s it returns an empty plan that `setPlan` would apply. `js_abort_probe.mjs` | Yes: "Re-plan failed" for some users and settings | Catch the abort and retry with another seed/gap; require optimal status or a small gap | Strong |
| 4 | Leakage: injury flags in backtests | **Critical** | Past flags are rebuilt from today's FPL notes (`news_added`). Only notes that turned out right survive: 62 of 62 flagged pool rows in GW3-7 really played 0 minutes (real flags at 25% are often wrong). Turning `hist_flags` off: corr 0.438 → 0.424, rank 0.553 → 0.528, picks 4.20 → 4.09 (2026/27; 2025/26 unaffected) | Inflates the bench, not live picks | Use `history/status.json` (collecting since 22 Oct) for past deadlines; until it covers the test weeks, report 2026/27 with `hist_flags` off | Strong (leak); Marginal (size: an upper bound) |
| 5 | Leakage: cleared-news rule | **Critical** (tiny) | `news_absences` adds GW7 to `ctx["out"]`, which the backtest's flag rule reads, so Gravenberch and Gibbs-White were projected 0.00 for GW7 (actual 0) instead of 2.18 and 3.46. Corr 0.438 → 0.437. The logged "unchanged" test toggled `news_abs`, which doesn't reach this path | Bench only | Keep `out_news` out of the set `hist_flags` reads | Strong |
| 6 | Planner vs optimiser captain/XI | High | `capPick` swaps a GKP/DEF captain for an attacker within 0.6 xP: captain differs in 18 of 80 balanced plan-weeks (−0.05 to −0.59 xP). `bestXI` ignores `haul_w`, `nail_w`, `hit_margin`: Safe XI differs in 39/80 weeks, captain 32/80; Chase 31/80 and 28/80 (e.g. GW9 Chase: optimiser Haaland 5.05, page Rudoni 4.10) | Yes: the captain and XI shown differ from the plan's | One captain/XI rule in both places (move the 0.6 swap into the optimiser or drop it; add the strategy terms to `adjXI`/`adjCap`) | Strong |
| 7 | Fixture difficulty under-reaction | Medium | Likely starters (start chance ≥ 0.8), both seasons, every position: FDR 4-5 over-projected +0.53 to +0.73, FDR 1-2 under −0.3 to −0.7 (exception: MID 26/27 easy +0.23). Raising team ratings to a power (1.25 / 1.5) doesn't fix it: corr +0.002 on 2025/26, captain −0.94 (CI −1.97 to −0.17) | Yes: fixture swings are undervalued in transfers | Not found yet. Next: test FPL's FDR (published before the GW) as an extra input, or a separate cs/attack fixture exponent | Marginal |
| 8 | Bench metric noise | Medium (process) | `pen_xg` 0.05 → 0 changes the captain in 7 of 35 weeks; cap Δ −0.63 (95% CI −1.69 to +0.23). Median gap between the top two projections is 0.21 pts. SD of captain points 4.55 → SE ≈0.77 for a 35-GW mean | Several "not adopted" decisions in the log rest on captain drops inside this noise | Report a paired bootstrap CI for captain/top-5 (`metric_noise.py`); decide on corr, rank and picks first | Strong |
| 9 | Build robustness | Medium | `crowd/latest.json` = `{"near": {}}` crashes the build (`KeyError: 'gw'`, line ~600). A corrupt `history/status.json` is silently replaced, wiping the injury log; it is written non-atomically. Missing odds change 372 players' xP with no warning on the site | Status-log loss would hurt the leak-free injury history | Guard the crowd block; write status.json via temp file + rename and refuse to overwrite if it fails to load; show a "no odds" note | Strong |
| 10 | Optimiser locks | Medium | Locks are dropped silently when the player is outside the candidate pool (non-playable, banned, 61st-ranked MID): plan returned without him. Browser adds locks to the pool correctly | None today (`build.py` passes no locks) | Add locked players to the pool or return None | Strong |
| 11 | Edge cases | Low | Undated 3-match ban assumed over after 2 games; status `i` with chance None → 50%; an impossible date in a news note ("30 Feb") raises and would crash the build; new signing with no data projects 0.00; FWD DC threshold learned as 16 (rule 12) from one data point, no metric change | Rare | Hard-code FPL DC thresholds; wrap `return_date` in try/except; treat `i` + None as 0 | Strong |
| 12 | Small optimiser/front-end mismatches | Low | Sell, re-buy, sell a profit player: optimiser £0.1m below FPL rule (pessimistic). `xp_detail` omits the 0.33 intercept so parts don't sum to xP. 14-man or duplicate-id squads accepted | None | Recompute bank as `bankAt`; add the intercept as its own part | Strong |
| 13 | Cheap enablers | Low | Under £4.5: −0.26 ± 0.04 (25/26), −0.13 ± 0.12 (26/27), persists half to half. Uses end-of-season price (hindsight) | Small: 9 weeks in the top 5 | Test a small trim on bench.py if wanted | Marginal |

## Checked and fine
- **FPL transfer rules:** the solver and `ftTable` match FPL's free-transfer rules in all 20 grid runs and 175 of 175 cases.
- **Hostile inputs:** lock/ban conflict, 4 locked from one club and an impossible budget all fail cleanly.
- **Python vs browser:** objectives are identical to 3 dp in all 10 comparable cases.
- **Constants:** `LAM`/`STRAT` match `MODES`/`STRATEGY`, slope 0.86 equals `cal_slope`, and bench weight, decay, FT value and hit cost agree.
- **Small or no leaks:**
  - DC thresholds as of each GW: no metric change.
  - Current-club xG: 10 rows moved, no metric change.
  - Odds: football-data's pre-closing averages, collected Fri/Tue, near the deadline.
- **Calibration:** refitting it on 2025/26 only and applying it to 2026/27 is slightly worse (RMSE 2.655 vs 2.653), so tuning on GW3-7 isn't inflating the bench.
- **Players:** no persistent player or archetype bias. Player residual half-to-half corr is 0.04. Haaland is +1.55 ± 0.84 on 2025/26 (as logged).
- **Sensitivity:**
  - Most fragile parameter: `home` ×0.8 (2025/26 corr −0.016).
  - `cs_k` ±20% moves corr by up to −0.005.
  - Everything else is within ±0.002 corr.
- **FPL's ep_next:** can't compare yet; there is no snapshot for a finished GW.

## Decision replay, 2025/26 GW4-38 (`decision_sim.py`)
Same GW4 wildcard squad for all, plan 5 GWs and execute 1, real points with auto-subs. No chips, no injury flags (the archive has none), EO = ownership.

| Strategy | Points | Hits | Moves | Captain = best in XI | Weekly SD | vs Balanced (95% CI) |
|---|---|---|---|---|---|---|
| Template (max ownership) | 1,993 | 5 | 37 | 20% | 14.4 | +125 (−80, +313) |
| Chase rank | 1,889 | 21 | 55 | 17% | 16.8 | +21 (−91, +141) |
| Play safe | 1,872 | 4 | 37 | 14% | 14.6 | +4 (−113, +117) |
| Balanced | 1,868 | 10 | 43 | 26% | 14.6 | — |
| Always roll (no transfers) | 1,791 | 0 | 0 | 26% | 16.8 | −77 (−258, +108) |
| Highest form | 1,729 | 66 | 101 | 26% | 16.6 | −139 (−319, +33) |

**Reading.** No strategy is clearly better than Balanced at 95%. Template's lead most likely comes from ownership knowing about injuries and team news, which the archive model can't see. The live model has flags, so this replay understates it. Re-run it on 2026/27 once the status log covers enough weeks. Coin flip.

## Scripts
`fetch_raw.py`, `common.py`, `leakage.py`, `mid_gw.py`, `metric_noise.py`, `edge_cases.py`, `calibration.py`, `sensitivity.py`, `decision_sim.py`, `adversarial.py`, `robustness.py`, `optimiser_stress.py`, `opt_inputs.py`, `js_parity.mjs`, `js_abort_probe.mjs`. Results are in `out/`.
