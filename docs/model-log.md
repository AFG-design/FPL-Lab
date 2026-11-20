# FPL Lab model log

## On probation (Adopt as Marginal): re-check list
Re-run each with `bench.py` at the stated time, candidate = the old value against main. Revert if the gain has gone.
- **cred_recency 0.9 for xG and DC** (adopted 14 Nov 2026, entry below). Re-check at GW20 (this season then has enough
  5-GW origins to count) and at season end. Old value to test against: `{"cred_recency": null}`. Adopted at pooled 5-GW
  +0.036 [-0.038, +0.114]; goals and DC part scores clearly better.
- **dc_prior_mins (FL-176)** (adopted 19 Nov 2026, entry below). Re-check at season end. Old value to test against:
  `{"dc_prior_mins": false}`. Adopted at pooled 5-GW −0.045 [−0.116, +0.023]; pooled DC part clearly better. It fixes a
  known error, so revert only if the DC part gain has gone, not on 5-GW picks alone.
- **archive_dc_backfill (FL-212)** (adopted 19 Nov 2026, entry below). Re-check at season end. Old value to test against:
  `{"archive_dc_backfill": false}`. Bench-fidelity change (does not move live projections); adopted at pooled 5-GW
  −0.006 [−0.038, +0.027] and pooled DC part −0.00015 [−0.00023, −0.00008] better. It fixes a known error (bench priors
  out of line with live), so revert only if the DC part gain has gone, not on 5-GW picks alone; reverting puts the bench
  back out of line with live.
- **dc_r 10 (FL-177)** (adopted 20 Nov 2026, entry below). Re-check at season end. Old value to test against:
  `{"dc_r": null}`. Targeted change (DefCon part): adopted at pooled DC part −0.00013 [−0.00021, −0.00006] better and
  pooled 5-GW +0.016 [−0.023, +0.058]. Revert if the DC part gain has gone.

What has been tested on the projection model, with results, so ideas aren't re-tried blindly.
Test bench: `bench.py` (rolling-origin backtest on this season, 2025/26 and 2024/25; past seasons carry betting odds
from odds/archive/ since PR #24, 31 Oct 2026).

## 20 Nov 2026 — FL-177: DefCon negative-binomial tail, `dc_r` 10 (Adopt as Marginal — targeted change, DC part)

- **Why:** the 18 Nov FL-114 follow-up (issue #194) benched the DefCon prior fix, `dc_r` 10 and `def_bonus_mult` 1.2
  together, so the tail's own effect was unknown. PR #28 (31 Oct, closed) tried `r` 5 in a bundle. FL-176 (prior fix)
  and FL-212 (2025/26 archive DefCon priors) are now on main, so this tests the tail **on its own**.
- **Change:** `fplmodel.p_at_least_nb(mu, k, r)`, a negative binomial tail with mean mu and size r (variance
  mu + mu²/r), computed with a stable pmf recurrence (no new dependency). `dc_tail` uses it for the DefCon chance
  only (`p_dc_model` and `p_dc_sub`, including the FL-080 `dc_fixture` path). Other `p_at_least` callers stay
  Poisson. Setting: `dc_r` (None = Poisson, the old behaviour; 0, negative or non-numeric raises; no silent fallback).
  **Identity check:** with `dc_r` None the bench "current model" lines and both backtest JSONs (with and without the
  status log) are byte-identical to main `2a20f73`.
- **Pre-registered variants (listed in the PR before running; no others):** V1 `dc_r` 5 (PR #28's value), V2 `dc_r`
  10 (#194's), V3 `dc_r` 20 (a mild tail), each against main (`dc_r` None). Not a package: `cs_k`, `dc_blend`,
  `def_bonus_mult` and `bonus_scale` are untouched (FL-160).
- **bench.py (candidate − main).** Only 2025/26 and this season score DefCon, so the **pooled DC interval is in effect
  2025/26 alone**; 2024/25 is identical to every printed digit for all three, as expected.

| | V1 r=5 | V2 r=10 | V3 r=20 |
|---|---|---|---|
| **Pooled DC part (Brier)** | −0.00016 [−0.00027, −0.00006] better | −0.00013 [−0.00021, −0.00006] better | −0.00009 [−0.00013, −0.00004] better |
| 2025/26 DC part | −0.00032 [−0.00054, −0.00011] | −0.00026 [−0.00041, −0.00012] | −0.00017 [−0.00027, −0.00009] |
| This season DC part | −0.00046 [−0.00090, −0.00005] | −0.00042 [−0.00068, −0.00019] | −0.00030 [−0.00044, −0.00017] |
| **Pooled 5-GW picks** | +0.017 [−0.017, +0.056] | +0.016 [−0.023, +0.058] | +0.003 [−0.029, +0.040] |
| 5-GW picks 2025/26 (main 18.96) | 18.99, +0.03 [−0.03, +0.11] | 18.99, +0.03 [−0.05, +0.12] | 18.97, +0.01 [−0.06, +0.08] |
| 5-GW picks this season (main 18.24, 4 origins) | 18.14, −0.10 [−0.27, +0.00] | 18.23, −0.01 [−0.03, +0.00] | 18.24, +0.00 [+0.00, +0.00] |
| 5-GW picks 2024/25 (main 19.16) | 19.16, +0.00 | 19.16, +0.00 | 19.16, +0.00 |
| 1-GW picks 2025/26 (main 4.46) | 4.45, −0.01 [−0.03, +0.01] | 4.46, −0.00 [−0.02, +0.01] | 4.46, −0.00 [−0.00, +0.00] |
| 1-GW picks this season (main 4.36) | 4.36, −0.01 [−0.07, +0.06] | 4.35, −0.01 [−0.06, +0.03] | 4.35, −0.01 [−0.07, +0.03] |
| Captain 2025/26 | −0.17 [−0.51, +0.00] (2 of 35 wks changed) | −0.03 [−0.09, +0.00] (1 of 35) | −0.03 [−0.09, +0.00] (1 of 35) |
| Top-5 2025/26 | +0.00 [−0.09, +0.09] | −0.03 [−0.09, +0.00] | −0.03 [−0.09, +0.00] |
| Captain / top-5 this season | +0.00 / +0.05 [−0.15, +0.30] | +0.00 / +0.05 [−0.15, +0.30] | +0.00 / −0.05 [−0.15, +0.00] |
| 5-GW corr (2025/26 / this season) | 0.522→0.521 / 0.583→0.582 | 0.522→0.522 / 0.583→0.582 | 0.522→0.522 / 0.583→0.583 |

  Every other part score is `+0.00000` in every season. bench.py has no pooled 1-GW interval (it pools 5-GW picks
  and part scores only), so 1-GW is per season. **No-harm:** no metric has its CI wholly below zero in any season for
  any variant. Near-misses: V1 this-season 5-GW −0.10 and V1 2025/26 captain −0.17, both with upper end +0.00.
- **backtest.py --compare, this season GW3–10** (without / with status log): **no segment past the limits for any
  variant.** Headline MAE: V1 1.8220→1.8300 / 1.7629→1.7704; V2 →1.8270 / →1.7676; V3 →1.8248 / →1.7655; corr ±0.0003.
  **2025/26 GW4–38 segment check** (as FL-176: scratch script, projections built as `bench.run_archive`, fed to
  `backtest.compare`; main reproduces FL-212's MAE 1.8636): no segment past the limits. MAE V1 +0.0056, V2 +0.0035,
  V3 +0.0020; largest segment moves top 30 ΔMAE V1 +0.017 / V2 +0.010 / V3 +0.001, DEF and MID bias ≤ +0.02.
- **DefCon calibration (raw real/projected, one-fixture weeks; 1.00 = right level):**

| Season | Segment | main | V1 r=5 | V2 r=10 | V3 r=20 |
|---|---|---|---|---|---|
| 2025/26 | all | 1.16 | 1.05 | 1.08 | 1.11 |
| | DEF | 1.09 | 1.03 | 1.05 | 1.06 |
| | MID | 1.25 | 1.07 | 1.13 | 1.18 |
| | top 30 | 0.89 ⚠ | 0.86 ⚠ | 0.88 ⚠ | 0.89 ⚠ |
| This season (no status log) | all | 1.22 | 1.02 | 1.08 | 1.14 |
| | DEF | 1.20 | 1.08 | 1.12 | 1.15 |
| | MID | 1.27 | 0.92 | 1.02 | 1.11 |
| | top 30 | 0.87 ⚠ | 0.84 ⚠ | 0.83 ⚠ | 0.84 ⚠ |
| This season (status log) | all | 1.27 | 1.05 | 1.12 | 1.18 |
| | DEF | 1.24 | 1.12 | 1.16 | 1.19 |
| | MID | 1.32 | 0.95 | 1.06 | 1.16 |
| | top 30 | 0.88 ⚠ | 0.88 ⚠ | 0.86 ⚠ | 0.87 ⚠ |

  ⚠ = below 0.95. **Main's top 30 is already below 0.95** (0.87–0.89: the top projected players are over-projected
  for DefCon, while the pool as a whole is under-projected). All three variants keep it below 0.95 and move it by
  −0.04 to 0.00. (#194's package went 1.03 → 0.87; main already sits at 0.87–0.89, which fits most of that drop
  coming from the prior fix rather than the tail.) The fatter tail lifts
  players short of the threshold and trims the near-certain ones only slightly, so it closes most of the pool-level
  gap without fixing the top-30 over-projection. That is a separate error (most likely the `dc_blend` shrinkage and
  the final calibration) and belongs to FL-160.
- **Live effect, V2 (GW11 build, 20 Nov, same data both sides):** next GW (GW11) xP mean +0.010, largest move +0.06;
  GW12 mean +0.010, largest +0.05. 5-GW xP moves by more than 0.1 for **100 of 473 players** (99 up, 1 down; 61 MID,
  39 DEF). Biggest risers are cheap MIDs at 9–10 DefCon per 90 who were short of 12: Ahoka +0.28 (DefCon chance
  0.11→0.17), Torp +0.23, Yates +0.23, Gourna-Douath +0.22; DEF Costinha +0.21, Netz +0.20. Only faller past 0.1: Hill
  −0.12 (0.60→0.58). Top-15 by position by 5-GW xP: 1 MID swapped, DEF and FWD unchanged; recommended plans unchanged.
- **Choice among qualifiers:** all three meet the targeted-change row. **V2 (`dc_r` 10) is adopted**: its DC gain
  is close to V1's (−0.00013 against −0.00016 pooled; the intervals overlap) with a tighter interval, and it avoids
  V1's near-misses (this-season 5-GW −0.10 [−0.27, +0.00], 2025/26 captain −0.17 [−0.51, +0.00]) and V1's MID
  overshoot this season (0.92). V3 gains less than half as much. Choosing among the qualifiers is a judgement call:
  the row allows any of the three.
- **Decision-table row:** `Targeted change: the targeted part's pooled interval is clear of zero in the right
  direction, the pooled 5-GW picks interval is not wholly below zero, and no segment worse` → **Adopt as Marginal**.
  Rating: **Marginal** (DC part clearly better; 5-GW picks interval includes zero). Re-check at season end against
  `{"dc_r": null}`. Next: FL-160 (clean sheets and defender scoring) builds on this, with `dc_r` 10 as its base.

## 19 Nov 2026 — FL-212: 2025/26 archive priors use FPL's backfilled 2024/25 DefCon (Adopt as Marginal — bench-fidelity change)

- **Context (logged in FL-176 below):** FPL backfilled 2024/25 `defensive_contribution` in `element-summary`
  `history_past` (`DC_FIRST = 2024`), so the live `priors.json` already has real 2024/25 DefCon. Vaastav's
  `2024-25/players_raw.csv` has no `defensive_contribution` column, so the 2025/26 test season's archive priors
  (2023-24 + 2024-25) still had `dc_mins = 0`, unlike the live model.
- **Change (one candidate only, listed before running: `{"archive_dc_backfill": true}` against main):**
  - Added `tools/dc_backfill.py` (rate-limited, same `MAX_FAILED = 2%` and `MIN_KEPT = 85%` guards as
    `make_priors.py`) and committed `archive_dc/2024-25.json` (**327** players with 2024/25 DefCon of 672 current
    players, 0 failed downloads). All 327 join 1:1 to vaastav's `2024-25/players_raw.csv` by FPL `code`, covering
    **303 of 415 (73.0%)** 2025/26 test-season players who had 2024/25 minutes (100% exact minutes match; test
    fails loudly below 70%). Players absent from the file (left the game) keep `dc_mins = 0`, as before.
  - `archive._priors()` merges `archive_dc/<season>.json` with the same 1:2 weights when a prior season (`>= DC_FIRST`)
    has no CSV `defensive_contribution` column, behind `DEFAULTS["archive_dc_backfill"]` (default `True`; `False`
    reproduces main exactly).
  - **Hindsight check:** only `season_name == "2024/25"` rows are extracted from `history_past` (2024/25 season
    totals, known before 2025/26 GW1). Nothing from 2025/26 or later enters `archive_dc/2024-25.json` or 2025/26's
    priors. Which players get a backfill is decided by who is still in FPL at the fetch (19 Nov 2026): 303 of 415
    (73%) 2025/26 test-season players with 2024/25 minutes. The other 112, mostly relegated or sold, keep
    `dc_mins = 0` as on main. That selection uses information from after 2025/26, but no 2025/26 outcome enters any
    value, and both sides are scored on the same players, so it is accepted for a bench-only change. 2024/25's test
    priors (`2022-23` + `2023-24`) never touch it.
  - **Bench-fidelity change only — live model unchanged:** `priors.json` is untouched and live GW11 5-GW xP moves
    for **0 of 672 players** (`max |Δ| = 0.0`). This changes how future tests are scored on 2025/26, not the live
    projections.
- **bench.py (candidate = `{"archive_dc_backfill": true}`, against main `f6d15e2`):**

| Season | 1-GW picks | 5-GW picks | 1-GW picks CI | 5-GW picks CI | cap CI | top-5 CI | DC part (Brier) CI |
|---|---|---|---|---|---|---|---|
| 2026/27 (4 origins) | 4.36 → 4.36 | 18.24 → 18.24 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00000 |
| 2025/26 | 4.46 → 4.46 | 18.97 → 18.96 | +0.00 [−0.03, +0.03] | −0.01 [−0.07, +0.05] | +0.03 [+0.00, +0.09] | −0.01 [−0.13, +0.10] | −0.00029 [−0.00046, −0.00016] |
| 2024/25 | 4.25 → 4.25 | 19.16 → 19.16 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00000 (no DefCon) |

  - **This season and 2024/25 are identical** to every printed digit.
  - **Pooled 2025/26 + 2024/25 (60 origins):** **5-GW picks −0.006 [−0.038, +0.027]** (includes 0, not wholly below);
    **DC part −0.00015 [−0.00023, −0.00008] better** (2025/26 second pool: `−0.00027 [−0.00041, −0.00014]` better).
    Every other part score `+0.00000`.
  - **No-harm:** 0 metrics with CI wholly below zero in any season (`cap` changed in 1 of 35 weeks in 2025/26,
    `+0.03 [+0.00, +0.09]`; 5-GW corr `0.522 → 0.522`).
- **Comparability:** 2025/26 bench figures from this PR on use the backfilled priors (5-GW picks `18.97 → 18.96`, DC
  part `0.0803 → 0.0800`), so earlier entries' 2025/26 numbers are not directly comparable.
- **Segments (2025/26 GW4–38, same check as FL-176):** 0 segments tripped (`n >= 30`, `ΔMAE > 0.05` or `|Δbias| > 0.2`).
  Headline MAE `1.8637 → 1.8636` (`−0.0001`), corr `0.4114 → 0.4114`, bias `−0.0309 → −0.0308`; DEF `ΔMAE −0.0009`,
  MID `+0.0004`, top 30 `−0.0217`. This season's backtest is identical with and without the status log.
- **Decision-table row:** meets both `CI includes zero, the change fixes a known error, and no segment worse` and
  `Targeted change: the targeted part's pooled interval is clear of zero in the right direction, the pooled 5-GW picks
  interval is not wholly below zero, and no segment worse` → **Adopt as Marginal**. Rating: **Marginal**.

## 19 Nov 2026 — FL-176: DefCon priors use DefCon minutes only (Adopt as Marginal)

- The error (logged before the fix: 31 Oct 2026 PR #28 entry, 18 Nov 2026 FL-114 follow-up): seasons with no
  defensive contributions counted as 0 DefCon. `archive._priors` divided DefCon by all minutes, `make_priors.py`
  counted a season with no field as 0, and `fplmodel` gave the DefCon prior the all-minutes weight
  (`w_last * min(1, mins / 1500)`), so DefCon priors were dragged towards 0.
- Fix (on its own, no tweaks): dc90 = DefCon / minutes of seasons that recorded it; `dc_mins` saved on the same
  per-season scale and 1:2 weights as `mins`; DefCon's prior weight is `w_last * min(1, dc_mins / 1500)` (0 when
  `dc_mins` is 0). A priors.json without `dc_mins` falls back to `mins`; validate.py warns with both counts.
  Switch `dc_prior_mins` (False = old behaviour, rebuilt exactly from the new prior fields; checked: the off-mode bench
  and backtests equal main's to every printed digit).
- Data found on 19 Nov 2026 (all 672 players' history_past): FPL backfilled DefCon for 2024/25 (no 900+ minute
  outfielder at 0; 7.22 DEF / 8.46 MID / 3.92 FWD per 90 against 7.80 / 8.48 / 4.42 in 2025/26). Every season before
  holds the field as 0 for everyone. So `DC_FIRST = 2024`: an earlier season is "not recorded" even with the field
  present. The vaastav archive has no DefCon column before 2025-26.
- Where it bites: **only the 2025/26 test season.** Its archive priors (2023-24 + 2024-25) had no DefCon, so every
  prior was a fake 0 at full weight; now DefCon gets no prior weight there. 2024/25 can't move: DefCon wasn't scored
  then, so its DefCon rate is 0 whatever the weight. **The live model doesn't move**: the live window (2024/25 +
  2025/26) recorded DefCon in both seasons, so the regenerated priors.json has `dc_mins == mins` for all 459 priors
  and identical dc90; GW11 5-GW xP changes for 0 of 672 players (max |Δ| 0.0). This season's backtest is identical
  with and without the status log.
- **bench.py (candidate = fix, against main):**

| Season | 1-GW picks | 5-GW picks | 1-GW picks CI | 5-GW picks CI | cap CI | top-5 CI | DC part (Brier) CI |
|---|---|---|---|---|---|---|---|
| 2026/27 (4 origins) | 4.36 → 4.36 | 18.24 → 18.24 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00000 |
| 2025/26 | 4.44 → 4.45 | 19.13 → 19.04 | +0.01 [−0.03, +0.05] | −0.09 [−0.23, +0.05] | −0.09 [−0.23, +0.00] | +0.15 [−0.03, +0.35] | −0.00137 [−0.00200, −0.00080] |
| 2024/25 | 4.25 → 4.25 | 19.16 → 19.16 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00000 (no DefCon) |

  Pooled 2025/26 + 2024/25: **5-GW picks −0.045 [−0.116, +0.023]** (includes 0, not wholly below); **DC part
  −0.00068 [−0.00099, −0.00040] better**. Every other part unchanged. No-harm: no CI entirely below zero (2025/26
  captain touches 0 at its upper end). 2025/26 5-GW corr 0.524 → 0.522.
- **Re-run after FL-213 merged** (2025/26 now with Europa and Conference League dates; same switch pairing): pooled
  5-GW picks **−0.063 [−0.133, +0.009]** (still includes 0); pooled DC part **−0.00069 [−0.00100, −0.00041] better**.
  2025/26: 1-GW picks 4.46 → 4.46, +0.00 [−0.03, +0.04]; 5-GW picks 19.10 → 18.97, −0.13 [−0.27, +0.01]; captain −0.09
  [−0.23, +0.00]; top-5 +0.15 [−0.03, +0.35]; DC part −0.00139 [−0.00202, −0.00083]. This season and 2024/25 are
  unchanged. 2025/26 segment check: no segment past the limits (MAE 1.8570 → 1.8640, DEF ΔMAE +0.014, top 30 +0.021);
  raw DefCon real/projected 1.39 → 1.16. Same decision row.
- **Segments.** `backtest.py --compare` on this season (with and without status log): identical, nothing flagged. Same
  segment check run on 2025/26 GW4–38 (scratch script feeding `backtest.compare`): no segment past the limits.
  Headline MAE 1.8586 → 1.8657 (+0.007), corr 0.4115 → 0.4111, bias −0.049 → −0.024; largest moves DEF ΔMAE +0.014,
  bias +0.045; top 30 ΔMAE +0.019, bias +0.050. Raw DefCon real/projected 1.38 → 1.15 (DEF 1.30 → 1.07, MID
  1.50 → 1.27).
- Decision: fixes a known error, CI includes zero, no segment worse → **Adopt as Marginal** (also meets the targeted
  change row: DC part pooled interval clear of zero, 5-GW picks not wholly below zero). Rating: **Marginal**.
- Note: this fix alone accounts for nearly all of the 18 Nov package V1's pooled 5-GW −0.047. The raw DefCon part is
  now much nearer real, yet final MAE edges up: settings tuned while DefCon was deflated (calibration slope/intercept,
  dc_blend, the Poisson tail) may now over-correct. That is for FL-160 (clean sheets and defender scoring) and FL-212
  (2024/25 DefCon rebuild test), not this item.

## 19 Nov 2026 — FL-213: 2025/26 Europa and Conference League dates added; `eu_cut` re-benched (no model change, data completed)

- **Data completed:** `openfootball/champions-league` still has no 2025/26 Europa League or Conference League files,
  so FL-115 (13 Nov 2026) ran 2025/26 with Champions League dates only. Added `europe_hist_manual.json` from UEFA's
  official 2025/26 match records (`match.uefa.com/v5/matches` / `uefa.com`, every stage including play-offs and the
  final) for the three English clubs: **AVL** (UEL, 15 dates: 2025-09-25 to 2026-05-20), **NFO** (UEL, 16 dates:
  2025-09-24 to 2026-05-07), and **CRY** (UECL, 17 dates: 2025-08-21 to 2026-05-27). `tools/europe_hist.py` now
  merges the supplement when openfootball 404s (openfootball still wins if published later), clearing `"missing"`
  to `[]`. 2025/26 European weeks in `bench.py`: 65 club-gameweeks (2024/25 unchanged at 49).
- **Measured (`tools/europe_check.py`, regulars' start rate in window / outside it; live cut implies 0.93):**
  - 2025/26: **1.056 [1.002, 1.110]** (530 player-games in window, 2,236 outside, 73 regulars), vs FL-115's
    `1.034 [0.969, 1.102]` (UCL only).
  - 2024/25: `0.980 [0.901, 1.055]` (393 in, 1,886 outside, 60 regulars; unchanged).
  - This season to GW10 (`europe.json`): `0.969 [0.890, 1.042]` (234 in, 576 outside, 81 regulars; unchanged).
- **Bench (`bench.py`, three variants only, listed before running: `eu_cut` 1.0, 0.98, 0.85 against live 0.93 on
  `main` `05edf5c`):**

  | Candidate | 2025/26 5-GW | 2024/25 5-GW | Pooled 5-GW (60 origins) | This season (4 origins) | Pooled Start Brier | CI wholly below zero |
  |---|---|---|---|---|---|---|
  | `eu_cut 1.0` | +0.02 [-0.09, +0.14] | -0.10 [-0.21, -0.01] | -0.040 [-0.118, +0.033] | -0.13 [-1.10, +0.68] | -0.00001 [-0.00010, +0.00009] | 2024/25 5-GW picks -0.10 [-0.21, -0.01] |
  | `eu_cut 0.98` | -0.03 [-0.13, +0.06] | -0.03 [-0.10, +0.03] | -0.030 [-0.092, +0.025] | +0.02 [-0.27, +0.22] | -0.00004 [-0.00011, +0.00003] | none |
  | `eu_cut 0.85` | -0.09 [-0.21, +0.04] | -0.05 [-0.13, +0.04] | -0.066 [-0.144, +0.010] | -0.11 [-0.55, +0.18] | +0.00042 [+0.00027, +0.00059] worse | 2024/25 1-GW picks -0.03 [-0.06, -0.00]; this season 1-GW picks -0.07 [-0.13, -0.01] |

  5-GW totals (2025/26 / 2024/25 / this season): live 0.93 `19.10 / 19.16 / 18.24`; 1.0 `19.12 / 19.06 / 18.11`;
  0.98 `19.07 / 19.14 / 18.26`; 0.85 `19.01 / 19.12 / 18.13`. 1-GW picks: live 0.93 `4.46 / 4.25 / 4.36`;
  1.0 `4.43 / 4.24 / 4.34`; 0.98 `4.46 / 4.24 / 4.36`; 0.85 `4.45 / 4.22 / 4.30`. Pooled 60+ minutes Brier also
  worsens at 1.0 (`+0.00024 [+0.00010, +0.00039]`) and 0.98 (`+0.00014 [+0.00005, +0.00024]`).
- **Decision-table rows (CLAUDE.md):**
  - `eu_cut 1.0` and `eu_cut 0.98`: **CI includes zero and the change is only a tweak (and doesn't qualify as a
    targeted change)** → **Don't adopt** (`1.0` also has 2024/25 5-GW picks wholly below zero).
  - `eu_cut 0.85`: **Any segment trips `--compare`** (no-harm rule: 1-GW picks CI wholly below zero in 2024/25 and
    this season) → **Don't adopt until it is fixed or explained.**
  - **Result: 0.93 still wins — no model change, data completed.** `eu_cut` left at 0.93.

## 18 Nov 2026 — FL-114 follow-up: defenders scoring outside clean sheets + cs_k retune (Don't adopt)

- Idea (FL-114 "Next lever"): clean sheets were over-projected in 2024/25 and 2025/26 (real/proj 0.90), yet fixing
  `cs_k` alone ranked defenders worse. Diagnostic on `main` (`c7fe6f5`) DEF one-fixture pool across all three
  seasons (2026/27 GW3–10 / 2025/26 / 2024/25, real/proj): goals `0.71 / 0.91 / 0.94` and assists
  `0.96 / 1.07 / 0.89` are not under-projected, whereas **defensive contributions** (`1.24 / 1.30 / –`, due to
  prior seasons without DC diluting `dc90` toward 0 and Poisson underestimating `>= 10` tail) and **DEF bonus**
  (`1.21 / 1.21 / 1.30`, from global `bonus_scale=0.8`) are consistently under-projected.
- Package (linked to rebalance defender scoring outside CS and retune `cs_k` with it; tested off `main` `c7fe6f5`,
  code reverted after testing):
  - `dc_prior_fix`: track `dc_mins` (only seasons with `defensive_contribution`) in `make_priors.py` and
    `archive.py` so 0-DC seasons don't shrink `dc90` toward 0; older `priors.json` without `dc_mins` falls back
    to `mins`, `dc_mins == 0` sets `wl = 0`. This part fixes a **known error**, not a tweak: the 31 Oct 2026
    PR #28 entry below already records that past seasons without DC gave players a DC rate of 0, and main still has
    it (`archive.py` adds up `dc_min` but divides `dc90` by all minutes; `make_priors.py` counts a season with no
    DC field as 0 DC). Bundled with the three tweaks here, its own effect is unknown; it is to be benched on its
    own as a known-error fix (follow-up task).
  - `dc_r = 10`: Negative Binomial tail in `p_at_least` (`None` or `<= 0` = Poisson).
  - `def_bonus_mult = 1.2`: scales DEF bonus to offset `bonus_scale=0.8`.
  - Not new: PR #28 (31 Oct 2026 entry below) already benched a Negative Binomial DC tail (r=5) and a higher
    `bonus_scale` (0.8 -> 0.95) as Marginal; main is still on Poisson and 0.8, so those were not kept. This run is
    a re-test of both ideas with different settings.
  - Three variants, listed before running: **V1** `cs_k=0.90`, **V2** `cs_k=0.95`, **V3** `cs_k=1.00`. Main already
    has `cs_k=0.9`, so V1 is the package alone with no clean-sheet retune (hence its CS log-loss `+0.00000`).
- **bench.py, pooled 5-GW picks (2024/25 + 2025/26, 60 origins, candidate − main):**
  V1 **−0.047 [−0.123, +0.023]**, V2 **−0.069 [−0.146, +0.005]**, V3 **−0.066 [−0.154, +0.021]**.
  Per-season 1-GW / 5-GW picks against main (`4.36 / 18.24` this season, `4.44 / 19.13` 2025/26, `4.25 / 19.16`
  2024/25):
  - V1: `4.36 / 18.24` (this season), `4.43 / 19.05` (`−0.08 [−0.22, +0.06]`, 2025/26), `4.25 / 19.15` (`−0.02 [−0.04, +0.00]`, 2024/25).
  - V2: `4.38 / 18.24` (this season), `4.44 / 19.04` (`−0.09 [−0.23, +0.05]`, 2025/26), `4.25 / 19.11` (**`−0.05 [−0.10, −0.01]`**, 2024/25).
  - V3: `4.38 / 18.24` (this season), `4.44 / 19.02` (`−0.11 [−0.27, +0.04]`, 2025/26), `4.25 / 19.14` (`−0.02 [−0.10, +0.06]`, 2024/25).
  - This season's difference intervals were not recorded, and the variant code and raw bench output were not kept,
    so the run can't be re-checked. This season's 5-GW total is `18.24` for main and all three variants.
- **Pooled part scores (lower loss is better):**
  - `Def. contribution` Brier: **−0.00068 [−0.00099, −0.00040]** better in all three (`2025/26` alone: `−0.00137 [−0.00200, −0.00080]`; 2024/25 has no DC).
  - `Bonus` sq. error: V1 `−0.00010 [−0.00033, +0.00012]`, V2 `−0.00014 [−0.00034, +0.00006]`, V3 `−0.00016 [−0.00033, +0.00001]` (2024/25 alone `−0.00020` / `−0.00021`, clear of 0).
  - `Clean sheets` log-loss: V1 `+0.00000`, V2 `−0.00061 [−0.00160, +0.00046]`, V3 `−0.00036 [−0.00232, +0.00175]` (but V3 current season `+0.00659 [+0.00052, +0.01198]` worse).
- **No-harm & `backtest.py --compare` (2026/27 GW3–10, with / without status log):**
  - No `--compare` segment trips in any variant (V1 MAE `+0.0013 / +0.0014`, V2 `−0.0053 / −0.0058`, V3 `−0.0109 / −0.0121`; corr `+0.0001 / −0.0002 / −0.0007`).
  - No-harm trips: V1 has `2025/26` `cap −0.34 [−0.77, −0.03]` and `2024/25` `top5 −0.06 [−0.13, −0.01]` wholly below zero; V2 has `2024/25` 5-GW picks `−0.05 [−0.10, −0.01]` wholly below zero; V3 worsens current-season CS log-loss (`+0.00659 [+0.00077, +0.01232]` with status log).
- **Decision-table rows:** pooled 5-GW picks CI includes zero in all three variants.
  - V1, V2: `Any segment trips --compare` (each has a no-harm CI wholly below zero, which counts as a tripped
    segment) → **Don't adopt** until fixed or explained.
  - V3: no no-harm trip under the rule (CS log-loss is a part score, not one of the listed no-harm metrics). Its DC
    part interval is clear of zero and its pooled 5-GW interval is not wholly below zero, but it is a package of a
    known-error fix plus three tweaks, not a change aimed at one part, so the targeted-change row doesn't apply;
    `CI includes zero and the change is only a tweak` → **Don't adopt.**

## 18 Nov 2026 — FL-173: returning regulars' start chance from last season (Don't adopt; issue #194 Item 1)

- Idea (FL-093 / FL-030 follow-up, the "Saliba problem"): a regular from last season on 0 minutes so far gets
  almost no start chance (Saliba: 1%, 0.34 xP over 5 GWs, 83% of games started last season). Lift his `p_start`
  towards last season's `start_rate` from priors.json. Run off main `a1a3efe` in an uncommitted worktree; code
  not merged, branch `feat/returning-regulars-start-prior` dropped.
- Three variants, listed before running: V1 `prior_start_games` 2 and V2 `prior_start_games` 5 (new param: last
  season's start rate fades out over that many uninjured club games, only for a player with no minutes in the
  window); V3 `start_prior` 2.0 (existing param, now also applied on top of xMins when the window is short).
- Live GW11 spot check (start chance / 5-GW xP): Saliba 0.013 / 0.34 → V1 0.423 / 7.13, V2 0.669 / 11.21,
  V3 0.560 / 9.40. Mitoma 0.006 / 0.19 → 0.579 / 7.23 in all three. V3 also lifts Minteh (8 minutes, 3 games)
  0.052 → 0.284, a false boost.
- **bench.py, pooled 5-GW picks (2024/25 + 2025/26):** V1 +0.000 [+0.000, +0.000], V2 +0.000 [+0.000, +0.000],
  V3 +0.015 [-0.004, +0.041]. Per season 1-GW / 5-GW against main 4.35 / 18.23 (this season), 4.44 / 19.13
  (2025/26), 4.25 / 19.16 (2024/25): V1 and V2 identical everywhere; V3 4.33 / 18.22, 4.45 / 19.14, 4.25 / 19.19.
- **Targeted part, start chance Brier (pooled, lower is better):** V1 +0.00000 [+0.00000, +0.00000],
  V2 +0.00000 [+0.00000, +0.00000], V3 +0.00039 [+0.00008, +0.00080] worse. FL-163 second pool: V1 −0.00002
  [−0.00006, +0.00001], V2 +0.00010 [+0.00001, +0.00026] worse, V3 +0.00051 [+0.00010, +0.00105] worse. This
  season's second pool: V1 +0.00038 [+0.00008, +0.00076] worse, V2 +0.00184 [+0.00042, +0.00374] worse.
- **Backtest (GW3–10, --compare):** no segment flags for any variant. With status log, V3 start Brier +0.00620
  [+0.00110, +0.01290] worse; all-players xMin MAE V2 +0.31, V3 +1.04; players outside the pool who played
  improve (V1 −0.55, V2 −0.94, V3 −1.33 xMin MAE, n=153) but less than everyone else gets worse.
- **Why the bench reads 0.000:** the deciding pool needs minutes in one of the last three GWs (see FL-163), so a
  0-minute player is outside it by construction. The evidence that decides this is the diagnostic, not the bench.
- **Diagnostic (why it fails):** players with a strong prior (start rate about 0.63–0.68) still on 0 minutes after
  2–4 uninjured club games start only 0–6% of the time this season, 2–9% in 2025/26 and 4–10% in 2024/25. Most are
  out of favour, not returning from injury, so pulling them to about 65% raises their start Brier from about 0.04
  to about 0.40. The diagnostic did not split them by why they had 0 minutes.
- Missing inputs: no priors.json or no `start_rate` falls back to minutes / 3230, or no blend if there are no
  minutes either; no history/status.json means injury weeks aren't removed from the game count. Both params
  default to 0 (off).
- **Decision-table row (all three): CI includes zero and the change is only a tweak (doesn't qualify as a targeted
  change: the start-chance interval is never clear of zero in the right direction) → Don't adopt.**
- Next: FL-174 re-tests the idea keyed to a recorded return from absence (status log `ret_why` back / date) rather
  than 0 minutes. Side finding, FL-175: with no minutes history, xMins gives unused bench players (Harwood-Bellis,
  Nunes) about 0.94 start chance; to be reproduced and fixed separately.

## 16 Nov 2026 — FL-162: walk-forward minutes retraining (Don't adopt)

- Protocol committed and draft PR #187 opened before training. Two linked minutes-package variants only:
  retrain all four boosters with the existing 21 inputs and fixed 320-round recipe; then the same with logistic
  start-chance recalibration fitted on the preceding season's out-of-sample predictions. Training through
  2023/24 → test 2024/25, through 2024/25 → test 2025/26, through 2025/26 → current season. No test-season fitting.
- **Pooled 5-GW picks, candidate − shipped:** retrained **−0.028 [-0.110, +0.052]**;
  recalibrated **−0.043 [-0.147, +0.060]**. Neither establishes an improvement.
- **Targeted start loss (lower is better):** retrained +0.000428 [-0.000145, +0.000970];
  recalibrated +0.010275 [+0.008964, +0.011623], clearly worse. Retrained 60+ Brier also worsens:
  +0.000551 [+0.000152, +0.000970]. The second regular-player pool confirms the same direction.
- **No harm / segments:** retrained 2024/25 correlation −0.001221 [-0.002388, −0.000059].
  Current-season top-30 MAE trips --compare in both variants: retrained +0.073 without flags / +0.128 with
  deadline flags; recalibrated +0.05034 / +0.089. Full before/after tables, all three seasons' 1-/5-GW totals,
  paired intervals and reliability bins: [FL-162 results](experiments/fl-162-results.md).
- Reliability example: shipped 2024/25 pool, 90–100% bin: mean predicted 93.16%, actual starts 93.57% (n=2,223).
  This does not support a blanket confidence squeeze. Recalibration learned on the earlier season did not transfer.
- **Decision-table row for both: any segment trips --compare → Don't adopt until fixed or explained.**
  Regressions remain unexplained; leave xmins/ and the separate xmins_sell shadow unchanged. No third variant tried.
- Worth it: keeps a reproducible walk-forward trainer and reliability report so the next refresh can be tested
  honestly. Newer training data alone are not a reason to replace the live model. The original training recipe
  was not supplied, so the same-season 2024/25 fold also measures reconstruction differences.
- Validation: 438-test Python suite passes plus the seven focused retraining tests (including output-path protection).
  Training/evaluation writes outside the repository; no history or live model file changes. Missing source labels,
  conditional targets or calibration classes raise. FL-163 coverage limits remain explicitly reported.

## 16 Nov 2026 — FL-163: second evaluation pool (report only)

- The deciding pool requires minutes in one of the last three gameweeks, so it omits returning regulars and
  qualifying arrivals. FL-137's outside-pool line only scores players who actually appeared: useful diagnosis,
  but not a pool that could have been chosen at the deadline.
- Added a second, report-only pool: the existing pool plus players with five starts in the previous ten gameweeks
  or at least 1,500 minutes in the immediately preceding season. Ten gameweeks includes blanks and sums starts in
  doubles; it is not ten appearances. Prior-only/returning eligibility requires a live row before the origin
  (zero-minute rows count as registration) or a deadline status-log entry. Membership stays fixed for all five
  weeks of a horizon. Future starts/results never admit a player, and non-appearances remain in the scores.
- Reports points, raw part scores and 1-/5-GW picks beside the current metrics; backtest also reports minutes
  accuracy. The existing deciding metrics, pooled intervals and model parameters are unchanged.

  | Season | Existing player-weeks | Second-pool player-weeks | Existing / second 1-GW picks | Existing / second 5-GW picks |
  |---|---:|---:|---:|---:|
  | 2026/27, GW3–10 | 3,050 | 3,344 | 4.36 / 4.36 | 18.24 / 18.24 |
  | 2025/26 | 12,847 | 14,456 | 4.44 / 4.44 | 19.13 / 19.13 |
  | 2024/25 | 13,003 | 14,573 | 4.25 / 4.25 | 19.16 / 19.16 |

- Coverage limits: no qualifying history means no membership, including overseas arrivals without a PL prior and
  arrivals not observed before the deadline. Missing prior/season dates cannot qualify a player via last-season
  minutes; stale two-season-old priors do not qualify. Missing one-week actuals are skipped; horizon blanks count
  as zero, as in the existing bench. Missing projections for eligible rows raise instead of silently dropping them.
- No adoption decision: evaluation tooling only. Whether this pool becomes part of the deciding metric remains
  the owner's decision. Comparing errors between the pools is not evidence of a model improvement: populations differ.

## 14 Nov 2026 — this-season cap lifted for xG and DC only (`cred_parts` ["xg", "dc"]; Marginal at 0.9, owner's call)

- Follow-up to the entry below: the cap lifted only where it helped (xG rate → goals, DC rate); bonus, saves, xA and
  cards keep it. Named as one package before running (both are steady-signal rates the all-rates test showed improving),
  variants cred_recency 0.9 / 0.95 / 1.0. These are variants 4-6 on this idea, chosen after seeing the first three, so a
  chance pass is likelier than the nominal rate.
- bench.py, 5-GW picks, candidate − main:

  | cred_recency | 2025/26 | 2024/25 | Pooled 5-GW | This season (4 origins) |
  |---|---|---|---|---|
  | 0.9 | +0.03 [-0.08, +0.16] | +0.04 [-0.05, +0.14] | +0.036 [-0.038, +0.114] | 0.00 |
  | 0.95 | -0.00 [-0.18, +0.16] | -0.05 [-0.13, +0.05] | -0.025 [-0.127, +0.067] | 0.00 |
  | 1.0 | -0.00 [-0.19, +0.17] | -0.11 [-0.26, +0.01] | -0.059 [-0.180, +0.050] | -0.11 [-0.47, +0.13] |

  5-GW totals (2025/26 / 2024/25 / this season): main 19.09 / 19.12 / 18.24; 0.9: 19.13 / 19.16 / 18.24; 0.95: 19.09 /
  19.08 / 18.24; 1.0: 19.09 / 19.01 / 18.13. 1-GW picks: main 4.46 / 4.24 / 4.33; 0.9: 4.44 / 4.25 / 4.36; 0.95: 4.45 /
  4.25 / 4.36; 1.0: 4.46 / 4.21 / 4.38. This season top-5 +0.50 to +0.60 (CI above 0, all three). No bench CI wholly
  below zero (1.0: 2024/25 1-GW picks -0.03 [-0.07, +0.00], close).
- Pooled part scores: goals -0.0006 [-0.0011, -0.0002] better at 0.9 (~0 at 0.95, 1.0); DC better at all three;
  every other part exactly unchanged. backtest.py --compare, with and without the status log: no segment past the
  limits; corr +0.0003 to +0.0005.
- Decision: 0.9 is the only variant with both past seasons positive and both target parts clearly better. Current rule:
  CI includes zero; Adopt as Marginal only if the cap counts as a known error (it was logged on 31 Oct before any fix;
  arguable). FL-161 proposal: qualifies as a targeted package (goals and DC clear, picks not wholly below zero) →
  Adopt as Marginal. Size: +0.04 real points per pick over 5 GWs, small. Owner approved 14 Nov: switched on as
  Marginal (on the re-check list at the top).

## 14 Nov 2026 — this-season cap lifted: `cred_recency` 0.9 / 0.95 / 1.0 (Don't adopt; setting left off)

- The problem (logged 31 Oct, before this fix): a rate = this season (each game x0.8 per GW back) + 600 pseudo-minutes
  of last season + 450 of the positional average. The weighted minutes never pass ~450, so this season is capped at
  ~30% of a rate however much he plays. `cred_recency` (None = old) keeps 0.8 for WHICH games count and weights his
  minutes by cred_recency per GW back for HOW MUCH this season counts (1.0: every minute, no cap).
- Three variants, listed before running. bench.py, candidate − main, 5-GW picks:

  | cred_recency | 2025/26 | 2024/25 | Pooled 5-GW | This season (4 origins) |
  |---|---|---|---|---|
  | 0.9 | -0.03 [-0.19, +0.13] | +0.01 [-0.11, +0.13] | -0.013 [-0.116, +0.093] | +0.07 [+0.00, +0.20] |
  | 0.95 | -0.11 [-0.31, +0.09] | -0.02 [-0.18, +0.13] | -0.067 [-0.202, +0.067] | +0.10 [-0.02, +0.22] |
  | 1.0 | -0.14 [-0.36, +0.09] | +0.03 [-0.19, +0.22] | -0.053 [-0.213, +0.098] | +0.10 [-0.02, +0.22] |

  5-GW totals main 19.09 / 19.12 / 18.24 (2025/26, 2024/25, this season); 0.9: 19.06 / 19.13 / 18.31; 0.95: 18.98 /
  19.10 / 18.34; 1.0: 18.96 / 19.16 / 18.34. 1-GW picks main 4.46 / 4.24 / 4.33; 0.9: 4.45 / 4.25 / 4.39 (this season
  +0.06 [+0.01, +0.12]); 0.95: 4.44 / 4.24 / 4.43 (+0.10 [+0.06, +0.14]); 1.0: 4.40 / 4.22 / 4.42 (+0.09 [+0.05, +0.14];
  2025/26 -0.06 [-0.12, +0.00]). No bench CI wholly below zero (no-harm passes, 1.0 only just).
- Pooled part scores (negative = better): goals -0.0006 [-0.0011, -0.0002] better at 0.9, ~0 at 0.95 and 1.0;
  DC better at all three; bonus worse at all three (+0.0009, +0.0020, +0.0040, each CI above 0); saves worse at all
  three; assists worse at 1.0. Clean sheets and minutes unchanged (they don't use these rates).
- backtest.py --compare, with and without the status log: no segment past the limits; headline corr +0.0005 to
  +0.0009, MAE -0.0006 to -0.0012.
- Read: the cap is real, but lifting it helps only the parts with a steady signal (xG, DC) and hurts the noisy ones
  (bonus, saves), where last season and the positional average are better guides. Picks don't gain in past seasons.
  This season looks better on 1-GW picks, but it has 8 weeks and doesn't decide.
- Decision: pooled 5-GW CI includes zero (point estimate negative for all three) → Don't adopt under the current
  rule. It wouldn't qualify as a targeted change under the FL-161 proposal either: it moves every rate, and three parts
  get worse. Setting left in the model, off. Possible follow-up (not run): lift the cap for xG and DC only.

## 14 Nov 2026 — FL-161: past "Don't adopt" results re-run under the proposed pooled rule (tooling; no model change)

- bench.py now prints a pooled 5-GW picks interval (2024/25 + 2025/26, GWs resampled within each season, then pooled)
  and a proper score per part (raw, before calibration) with paired intervals. All 14 past rejections still expressible
  as a setting were re-run on main (5-GW picks per season and pooled, candidate − main; part score pooled, negative =
  better):

  | Candidate | Targets | 2025/26 | 2024/25 | Pooled 5-GW | Pooled part score | Proposed rule |
  |---|---|---|---|---|---|---|
  | cs_k 0.95 | clean sheets | +0.02 [-0.02, +0.07] | -0.06 [-0.12, -0.00] | -0.018 [-0.054, +0.017] | CS log-loss -0.0006 [-0.0016, +0.0005] | Don't adopt (same) |
  | cs_k 1.0 | clean sheets | +0.03 [-0.04, +0.10] | -0.08 [-0.15, -0.00] | -0.024 [-0.073, +0.025] | CS log-loss -0.0004 [-0.0023, +0.0018] | Don't adopt (same) |
  | home 1.12 | none | -0.05 [-0.16, +0.04] | +0.05 [-0.05, +0.15] | -0.003 [-0.077, +0.070] | – | Don't adopt (same) |
  | home 1.20 | none | -0.07 [-0.25, +0.08] | +0.09 [-0.06, +0.26] | +0.008 [-0.117, +0.121] | – | Don't adopt (same) |
  | goal_mult 1.0 | goals | +0.06 [-0.04, +0.17] | -0.03 [-0.10, +0.03] | +0.016 [-0.046, +0.075] | goals dev. +0.0007 [-0.0001, +0.0015] | Don't adopt (same) |
  | assist_mult 1.0 | assists | -0.01 [-0.10, +0.07] | -0.02 [-0.11, +0.07] | -0.018 [-0.081, +0.043] | assists dev. +0.0041 [+0.0030, +0.0052] worse | Don't adopt (same) |
  | eu_cut 1.0 | start chance | +0.03 [-0.06, +0.14] | -0.10 [-0.17, -0.03] | -0.032 [-0.091, +0.031] | start Brier +0.00004 [-0.00003, +0.00010] | Don't adopt (same) |
  | eu_cut 0.98 | start chance | +0.01 [-0.07, +0.10] | -0.09 [-0.16, -0.03] | -0.042 [-0.091, +0.015] | start Brier 0.00000 [-0.00004, +0.00005] | Don't adopt (same) |
  | eu_cut 0.85 | start chance | +0.01 [-0.07, +0.09] | -0.01 [-0.12, +0.10] | -0.003 [-0.070, +0.062] | start Brier +0.0002 [+0.0001, +0.0003] worse | Don't adopt (same) |
  | team_recency 0.95 | none | +0.00 [-0.02, +0.03] | +0.01 [-0.04, +0.07] | +0.008 [-0.021, +0.040] | – | Don't adopt (same) |
  | team_recency 0.97 | none | -0.00 [-0.04, +0.04] | -0.06 [-0.16, +0.04] | -0.029 [-0.087, +0.021] | – | Don't adopt (same) |
  | pen_xg 0.15 | goals | -0.02 [-0.11, +0.07] | +0.03 [-0.11, +0.17] | +0.002 [-0.077, +0.077] | goals dev. +0.0006 [+0.0001, +0.0010] worse | Don't adopt (same) |
  | start_prior 0.5 | start chance | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 | Don't adopt (same; no effect with xMins on) |
  | min_window 7 | start chance | +0.01 [-0.02, +0.05] | -0.01 [-0.03, +0.00] | -0.001 [-0.020, +0.020] | 0 | Don't adopt (same) |

- None would be decided differently. Pooling narrows the 5-GW interval by about a third (cs_k 1.0: widths 0.14 and
  0.15 per season, 0.10 pooled). The part scores are far more precise than picks: they show the current assist_mult,
  eu_cut and pen_xg beat the alternatives on their own part, and that cs_k 1.0 fixes the clean-sheet level without
  forecasting clean sheets any better (log-loss unchanged). home and goal_mult figures differ slightly from the
  13 Nov entry, which ran before the European cut was in the bench. start_prior and min_window no longer do anything
  with xMins on (left in the model; candidates for removal).
- 2024/25 has no defensive contributions (DC score 0 on both sides), so read DC on 2025/26 only.

## 14 Nov 2026 — FL-127: Strong / Marginal / Coin flip cut-offs tested (labels only; one-week scale changed)

- tools/verdict_check.py rebuilds Home's three calls out of sample on 2024/25 and 2025/26 (plus this season, GW3 to
  10), with the model's own squad from three weeks earlier (the archive has no ownership or per-week prices, so squads
  and the £0.5m price limit on transfers are assumed). A call "comes off" when the chosen option really scored more.
  One captain and one lineup call a week is too few (67), so every comparable pair is also counted (any two of the
  five best starters; a low starter v a sub). 95% intervals by bootstrap over weeks. Pooled:

  | Call | Projected gap | Came off | Real gain |
  |---|---|---|---|
  | Captain-like pairs (670) | under 1.5 | 56% [51, 61] | +1.30 |
  | | 1.5 to 2 | 62% [45, 75] | +1.94 |
  | | 2+ | 79% [55, 97] | +6.30 |
  | Lineup-like pairs (804) | under 1.5 | 51% [45, 58] | +0.26 |
  | | 1.5 to 2 | 60% [49, 70] | +0.58 |
  | | 2+ | 76% [68, 83] | +2.57 |
  | Transfer over 5 GWs (504) | under 1 (Coin flip) | 51% [39, 64] | +0.06 |
  | | 1 to 3 (Marginal) | 54% [46, 63] | +1.55 |
  | | 3+ (Strong) | 65% [60, 71] | +5.64 [+3.83, +7.52] |

- The old one-week cut-offs (Strong at 1, Marginal at 0.4) didn't separate: Coin flip 52-55%, Marginal 53-59%,
  Strong 60-64%. The same pattern holds in each past season on its own (captain and lineup pairs: 1 to 1.5 came off 48-54%,
  1.5 to 2 60-64%, 2 to 3 71-76%). Changed to
  Strong 2, Marginal 1.5 (CUT_WEEK in site/js/core/plan.js) for Home's captain and lineup cards and the Planner's
  captain cards. Transfers keep 3 / 1 (they separate). The no-moves (Roll) card's own scale and the AFG lean scale
  (a fun layer, FL-132) were not tested and are unchanged.
- Consequence: captain calls will mostly read Coin flip. The captain v vice gap was under 1.5 in 66 of 67 weeks, and
  those calls came off 45% of the time. That is the honest reading of a one-week call, not a fault in the labels.

## 14 Nov 2026 — FL-114 (second slice): league goal level, cs_k and planner settings (no change; Don't adopt)

- **League goal level** (tools/team_level_check.py: each match projected before it was played, `use_flags=False`,
  real/projected with a bootstrap 95% CI over GWs): goals 0.97 [0.91, 1.02] (2024/25), 0.98 [0.92, 1.05] (2025/26),
  0.91 [0.79, 1.05] (this season, GW4 on). Calibrated, so no change. The old audit's "about 10% high" was from before
  upcoming fixtures used betting odds.
- **Clean sheets** (cs_k 0.9, CS chance = exp(−cs_k × goals against)): over-projected in both past seasons, real/proj
  0.85 [0.76, 0.96] (2024/25) and 0.80 [0.70, 0.90] (2025/26); this season 1.04 [0.76, 1.27]. Worst at FDR 4–5
  (projected 0.199 v real 0.132 in 2024/25, 0.197 v 0.118 in 2025/26). cs_k 1.0 fixes the level (0.97, 0.91; this
  season 1.19) but bench.py, candidate v main, 5-GW picks:

  | Candidate | 2024/25 | 2025/26 | This season | Result |
  |---|---|---|---|---|
  | cs_k 0.95 | -0.06 [-0.12, -0.00] | +0.02 [-0.02, +0.07] | 0.00 (4 origins) | Don't adopt (tweak; CI below zero in 2024/25) |
  | cs_k 1.0 | -0.08 [-0.15, -0.00] | +0.03 [-0.04, +0.10] | 0.00 (4 origins) | Don't adopt (tweak; CI below zero in 2024/25) |

  5-GW totals main / 0.95 / 1.0: 19.12 / 19.07 / 19.05 (2024/25), 19.09 / 19.12 / 19.12 (2025/26), 18.23 all three
  (this season). 1-GW picks within ±0.01, CIs cross zero. The CS over-projection is real but appears to offset
  defenders being under-projected elsewhere; fixing CS alone ranks defenders worse. Next lever: how defenders score
  outside clean sheets (defensive contributions, attacking returns), then retune cs_k with it.
- **Planner settings, report only** (tools/planner_replay.py overrides an optimise.py constant for one run; optimise.py
  unchanged). strategy_replay on 2025/26 and 2024/25, real points per season v current settings, paired mean ± 95%:

  | Strategy | Setting (current) | Candidate | Real pts/season v current | Result |
  |---|---|---|---|---|
  | Balanced | MIN_PROFIT (1.0) | 0 | -45.2 ± 14.6 (worse in all 6 runs) | Keep 1.0 |
  | Balanced | MIN_PROFIT | 2 | -34.0 ± 33.2 | Keep 1.0 |
  | Balanced | BENCH_W (0.1) | 0.05 | -7.3 ± 34.5 | Keep 0.1 |
  | Balanced | BENCH_W | 0.2 | -21.7 ± 55.1 | Keep 0.1 |
  | Chase | HIT_GAIN (2.0) | 1.0 | +7.0 ± 17.1 (+0.8 hits a season) | Keep 2.0 (no clear gain) |
  | Chase | HIT_GAIN | 3.0 | 0 (Chase took no hits at 2.0 either) | Keep 2.0 |
  | Chase | CHASE_BUDGET (2.0) | 1.0 | -39.0 ± 46.7 | Keep 2.0 |
  | Chase | CHASE_BUDGET | 3.0 | -34.8 ± 36.3 | Keep 2.0 |

  Balanced: 3 seeds × 2 seasons, 600 sims; Chase: 2 seeds × 2 seasons. The current values are best or level on every
  row, so nothing to change. FL-114 is now complete.
## 13 Nov 2026 — FL-114 (first slice): five untested settings benched (no change; Don't adopt)

- Settings with no result in this log (or only a ±20% sensitivity check), picked by how much they move points, plus
  xmins_skip_out from FL-094. bench.py on all three seasons, candidate v main, 5-GW picks (deciding; this season
  doesn't decide at 4 origins) and anything else with its CI wholly below zero:

  | Candidate | 2024/25 | 2025/26 | This season | Result |
  |---|---|---|---|---|
  | home 1.12 (now 1.05) | +0.01 [-0.08, +0.11] | -0.07 [-0.17, +0.02] | +0.19 [+0.01, +0.37] | Don't adopt (tweak) |
  | home 1.20 | +0.10 [-0.01, +0.21] | -0.07 [-0.26, +0.09] | +0.25 [+0.09, +0.43]; 1-GW picks -0.03 [-0.05, -0.01] | Don't adopt (tweak; trips no-harm) |
  | xmins_skip_out on | 0 [0, 0] | 0 [0, 0] | -0.05 [-0.15, 0.00] | Don't adopt (archive has no injury flags) |
  | goal_mult 1.0 (now 0.88) | +0.04 [-0.00, +0.09] | -0.04 [-0.19, +0.12] | +0.34 [+0.01, +0.64] | Don't adopt (tweak) |
  | assist_mult 1.0 (now 1.2) | -0.03 [-0.11, +0.06] | -0.02 [-0.10, +0.06] | +0.02 [-0.25, +0.27] | Don't adopt |

- 5-GW totals at main (bench without the European cut, as before FL-115): 17.98 (this season), 19.13 (2025/26), 19.03 (2024/25). home and goal_mult look better this season
  only; re-check both about GW20, when this season has enough 5-week forecasts to count. The penalty bonus (pen_xg)
  was left out: already tested (no clear effect, model log above). League goal level, cs_k and the planner settings: see
  the second slice above.
## 13 Nov 2026 — FL-094: a team-mate returning, diagnosed (no model change; Don't adopt)

- The item: lower a stand-in's minutes when the regular he covered for comes back. Its example was wrong (Konsa is at
  Aston Villa, Saliba at Arsenal), so it was checked before building.
- First check (tools/returning_mates.py, first version): a "return" = a regular back after 2+ weeks with 0 minutes who
  then STARTS. Stand-ins over-projected +18.9 minutes [12.8, 24.8] (2024/25) and +13.6 [9.2, 18.6] (2025/26) beyond
  players like them; returners projected at a 15% start chance. A position cap (a club's projected starters held to
  the number it uses) changed nothing, because the returner wasn't projected to start.
- Why: that definition picks events by their outcome (he started, so his stand-in was benched), and the archive has
  no injury flags, so a past regular's injury weeks look like being dropped. Not the model's error.
- Honest check (this season only, from the status log): a return = flagged at the previous deadline, cleared at this
  one, started or not. 11 regulars: start chance 0.54 v 73% started, xMin 49 v 55. Their 15 stand-ins: 0.48 v 53%
  started, xMin 45 v 53 — not over-projected at all. With xmins_skip_out (injury weeks left out of the xMins
  history): returners 0.58, xMin 53 v 55; stand-ins unchanged.
- Decision: no change (the cap code was removed, not shipped). Too few honest returns to tune on (11); the mild
  under-projection of returners goes to FL-114 (xmins_skip_out). Re-run tools/returning_mates.py around GW20.
## 13 Nov 2026 — FL-115: European rotation cut tested; kept at 0.93 (no model change; Don't adopt the alternatives)

- The cut (a starter's start chance x0.93 in a league game from 2 days before to 3 after a European match; 70% of the
  rested starts come off the bench) had never been tested: backtest.py and bench.py never built the European weeks,
  so every past figure ran without it. Now both do (europe.json this season; europe_hist.json, from openfootball's
  public-domain fixture lists, for 2024/25 all three competitions and 2025/26 the Champions League only: its Europa
  and Conference League files aren't published). It is a setting, eu_cut (0.93 = live, unchanged: the same GW11
  projection to 0.0 xP for all 672 players).
- Measured (tools/europe_check.py): regulars' start rate in the window / outside it 0.980 [0.901, 1.055] (2024/25),
  1.034 [0.969, 1.102] (2025/26), 0.969 [0.890, 1.042] (this season to GW10). Barely any fewer starts.
- Bench, candidate v 0.93, 5-GW picks (deciding) and anything else with its CI wholly below zero:
  - 1.0 (no cut): 2024/25 -0.10 [-0.17, -0.03]; 2025/26 +0.03 [-0.06, +0.14] with top-5 -0.21 [-0.42, -0.05].
  - 0.98 (the measured rate): 2024/25 -0.09 [-0.16, -0.03]; 2025/26 +0.01 [-0.07, +0.10] with top-5 -0.14 [-0.30, -0.00].
  - 0.85: 2024/25 -0.01 [-0.12, +0.10]; 2025/26 +0.01 [-0.07, +0.09]; this season -0.28 [-0.57, -0.03] (4 origins).
- So the cut earns its place on picks although starts barely fall: it marks down players at European clubs in weeks
  they disappoint for other reasons (tired legs, early subs), which the start rate doesn't see. Weaker is worse,
  stronger no better. Decision: keep 0.93; removing or retuning → Don't adopt. Bench figures from now on include
  the cut, so they differ slightly from older entries. Re-run tools/europe_check.py and the bench at season end.

## 13 Nov 2026 — FL-053: double gameweeks diagnosed (no model change; Don't adopt)

- The 1 Nov check found double-gameweek players under-projected (xP 4.64 v 4.84 real in 2025/26, 4.44 v 5.00 in
  2024/25). FL-053 asked which part. tools/dgw_check.py (honest 1-GW forecasts, pool players):
  - by part, real/projected (raw), singles v doubles: appearance 0.95 v 0.96 / 0.95 v 0.94 (no extra rotation across
    the two games), bonus 1.19 v 1.27 / 1.22 v 1.35, goals 1.02 v 1.05 / 1.03 v 1.55, assists 1.14 v 1.08 /
    1.09 v 1.54 (2025/26 / 2024/25). The calibration adds its intercept per match, so it treats doubles as two singles.
  - the same clubs' single-match weeks within 4 GWs of their double: gap (real - xP per player-week) +0.04 [-0.17,
    +0.23] in 2025/26 and +0.30 [+0.11, +0.48] in 2024/25; the doubles +0.20 [-0.10, +0.63] (+0.10 a match) and
    +0.56 [-0.21, +1.17] (+0.28 a match). In 2024/25 the clubs were under-projected by the same amount a match
    whether they played once or twice: the clubs that get doubles (cup runs), not the double.
- No part is off in a way that is specific to doubles and holds in both seasons; 3-4 double gameweeks a season (190
  player-weeks) can't separate a few tenths of a point from noise. No fix made, so nothing to backtest or bench (the
  model is unchanged). The club effect overlaps FL-129 (top-end under-projection, on hold).
- Decision: no change → Don't adopt. Re-run tools/dgw_check.py once this season has double gameweeks, adding them.

## 13 Nov 2026 — FL-080: defensive contributions per fixture, no 60-minute gate (Adopt as Marginal, check carefully)

- Known error (traced, backlog FL-080: fplmodel L644-650, L702): the DefCon chance was learned from gameweeks where he
  played 60+ (a double summed into one "week") and applied only to 60+ minute appearances. FPL's rules have no minutes
  gate, and a double is two chances. Now (dc_fixture; False = old): chance per START from his own starts fixture by
  fixture (any length), blended with the rate model; per SUB appearance from the rate model at his bench minutes.
- Backtest vs main (GW3-10): with status log MAE 1.7653 → 1.7665, corr 0.4437 → 0.4442; without 1.8245 → 1.8259,
  0.4277 → 0.4283. Raw DefCon part real/projected 1.30 → 1.26 (mse −0.001); DEF MAE +0.004. No segment past the limits.
- Per kind of appearance (raw DefCon points per player-week, projected v real): this season starts 0.240 → 0.244 v
  0.362, subs 0.045 → 0.050 v 0.003; 2025/26 doubles 0.326 → 0.328 v 0.366 (n=186). Subs almost never earn it (real
  0.3-0.6% of sub appearances), so the rule fix adds little; starts remain under-projected before calibration.
  2024/25 had no DefCon scoring (0 everywhere).
- bench.py (new − old): 5-GW picks this season −0.13 [−0.38, 0.00] (4 origins), 2025/26 +0.00 [−0.05, +0.04],
  2024/25 +0.00 (no DefCon); 1-GW picks this season −0.01 [−0.03, 0.00]; 2025/26 captain +0.03 (1 of 35 weeks changed).
- Live build: 135 players' 5-GW xP move (mean 0.03; Sangaré +1.17, Mendy −0.86); plans make the same moves. dc_rate
  (shown on the site) is now per start, and the player sheet says so.
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal. Check carefully: this season's
  5-GW point estimate is −0.13 (CI touches 0); re-check at GW20.
## 13 Nov 2026 — FL-030: new signings (Adopt as Marginal, check carefully)

- What was wrong (backlog FL-030 and FL-082's "new-signing minutes defaults", recorded before the fix): a player new to
  the Premier League got the minutes model's no-history output, unmarked. The backlog expected "about a 5% start chance";
  measured since the xMins model, it is the opposite: arrivals (no PL minutes in the two seasons before) averaged a 0.28
  to 0.33 start chance in their first 5 games but started 0.10 to 0.16 (most are academy and back-up players).
- Fix (new_signings; False = old): an arrival gets a start chance from his price band (ARRIVAL_START: £4.5m or less 0.07,
  £4.6-5.4m 0.23, £5.5-6.9m 0.21, £7.0m+ 0.30; share of first-5 games started by 2022/23-2023/24 arrivals, so the bench
  seasons are out of sample), fading over his first 5 registered club games and only until he first plays. Marked
  assumed on the player sheet (arrival, start_assumed; validate checks it). A mover within the PL keeps his weeks at
  his old club in both minutes models (ctx["moved"] from FL-065's clubs_then; no case this season).
  A first version kept the guess after he had played: it dragged promoted clubs' regulars down (pool corr 0.444 -> 0.434)
  and was dropped.
- First-5-games check for arrivals (old -> new): start chance v started 0.33 -> 0.18 v 0.16 (this season), 0.29 -> 0.14
  v 0.11 (2025/26), 0.28 -> 0.13 v 0.10 (2024/25); start Brier 0.237 -> 0.069, 0.214 -> 0.055, 0.197 -> 0.042; xP MAE
  1.202 -> 0.746, 0.935 -> 0.549, 0.853 -> 0.483.
- Backtest vs FL-065 (pool): identical with and without the status log (the pool is players who played in the 3 GWs
  before, so the guess is already off). Not in pool, played: xMin MAE 29.7 -> 26.7, start Brier 0.260 -> 0.217.
- bench.py: pool metrics and 5-GW picks identical in all three seasons (CI [0, 0]): the deciding metric can't see
  arrivals by construction. All players MAE 1.753 -> 1.747, 1.845 -> 1.844, 1.748 -> 1.747.
- Decision: CI includes zero; no segment worse; the old silent no-history default was recorded (FL-082 audit) before
  the fix, so Adopt as Marginal. The price bands themselves are a fitted heuristic: re-check after January.

## 13 Nov 2026 — FL-065: past xG and opponents follow the club he played for that week (Adopt as Marginal)

- Known error (traced 5 Nov, backlog FL-065: fplmodel L265-270, L564-565): the live model credited every past week's xG
  to a player's current club and judged his past form against his current club's opponents. 17 summer movers carried
  0.98 xG of GW1-2 into their new clubs' attack ratings. FL-068 fixed this for backtests only; now the live model uses
  the same clubs_then (xg_club_then; False = old). Ambiguous club (one game at a club he has since left): his xG goes to
  no club and his opponent adjustment is off that week; build.py lists them in meta.club_ambiguous and validate warns
  (none today). The Fixtures team trend uses the same per-week club.
- Backtest vs main (honest, GW3-10): identical with and without the status log (MAE 1.7653 / 1.8245): the backtest
  already credited xG to the club then (FL-068), and the opponent part moves nothing measurable for 17 players.
- bench.py (xg_club_then off = the live model's old behaviour, club at each forecast's deadline): 5-GW picks new − old
  2024/25 +0.01 [0.00, +0.01], 2025/26 +0.00, this season +0.00; 1-GW picks ±0.00; captain unchanged in every week.
- Live build: 459 of 472 players move through the team ratings, mean |Δ 5-GW xP| 0.002, largest +0.04 (Muharemović);
  plans make the same moves and captains.
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal.

## 13 Nov 2026 — FL-031: injury adjustments tested one at a time (no change; Don't adopt)

- On the honest backtest (FL-068, status log, GW3-10, n=3050), each rule switched off on its own. `doubt_abs` split
  from `late_abs` so the doubtful-flag rule can be tested apart from the late-news rule (both stay on).
  | switched off | MAE | corr | flagged MAE | returning players xMin MAE |
  |---|---|---|---|---|
  | none (FL-068) | 1.7649 | 0.4437 | – | 10.26 (n=120) |
  | return_ramp (1.0, 1.0) | 1.7654 | 0.4437 | +0.013 | 10.58 (n=120) |
  | late_abs | 1.7649 | 0.4440 | −0.001 | 9.19 (n=97) |
  | doubt_abs | 1.7658 | 0.4432 | +0.011 | 6.89 (n=97; a different, smaller set) |
  No segment past the limits in any run.
- bench.py: this season no pick, top-5 or captain changes in any week (every paired CI [0, 0], 5-GW picks 18.11 in all
  four). 2025/26 and 2024/25 identical: the archive has no flags or news, so none of the three rules can fire there. The
  past-season test the decision table needs can't be run until the status log covers a full season.
- No double count shows: switching one rule off never improves the total by more than noise (late_abs corr +0.0003,
  MAE ±0). return_ramp and doubt_abs each still earn a little; late_abs is neutral.
- Decision: removing late_abs would only be a tweak (no rule broken) with CI [0, 0] → Don't adopt. All three kept.
  Re-test at about GW20 with twice the weeks, and next season on 2026/27 with its full status log.

## 13 Nov 2026 — FL-079: goalkeeper saves for a start and a sub appearance separately (Adopt as Marginal)

- Known error (reproduced, backlog FL-079): save points (1 per 3 saves) were one Poisson on his expected minutes, which
  spreads the minutes over the cases where he doesn't play. A save point needs 3 saves in the minutes he does play, so
  below 100% it was understated: 50% to start, about 3 saves a game, 0.20 v 0.33. Now start and sub appearance are
  worked out separately and weighted by their chances (save_split; False = old).
- Backtest vs FL-068 (GW3-10): with status log MAE 1.7649 → 1.7653, corr 0.4437 both; without 1.8239 → 1.8245. Raw
  saves part real/projected 1.13 → 1.08 (was under-projected; mse −0.004). GKP MAE +0.008 / +0.010 (n=172, under the
  limit) after calibration; top 30 MAE −0.012. No segment past the limits.
- bench.py (new − old): 5-GW picks 2024/25 +0.02 [0.00, +0.06], 2025/26 +0.00 [0.00, 0.00], this season +0.00; 1-GW
  picks 2024/25 +0.01 [0.00, +0.02]; captain unchanged in every week; GKP corr ±0.001.
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal.

## 13 Nov 2026 — FL-067: return date checked before the 50% no-chance default (Adopt as Marginal)

- Known error (reproduced, backlog FL-067): a flagged player with no chance given got our 50% default for next GW even
  when FPL's own return date was after the kick-off ('Suspended until 21 Nov', game 20 Nov: 50%, should be 0).
  Fixed in availability_info: kick-off before the date -> 0 (FPL's date, not assumed). No date, a date that has passed,
  or no kick-off keep the 50% default, marked assumed.
- Projections unchanged today and in every backtest week: this season FPL gave a chance (0) with every i/s/n flag
  (status log: 0 rows with no chance; news log: 0), and the backtest path rules a flagged player out at his deadline
  anyway (hist_flags). Backtest vs FL-068: identical with and without the status log (MAE 1.7649 / 1.8239). bench.py:
  identical on all three seasons (5-GW picks 18.11 / 19.13 / 19.01; every CI [0, 0]).
- Decision: CI includes zero, fixes a known error, no segment worse -> Adopt as Marginal.

## 13 Nov 2026 — FL-131: xmins_sell shadow re-landed (shadow only; no live change)

- PR #29 (31 Oct) was closed unmerged on 12 Nov, so no shadow had been saved before any deadline. Re-landed on current
  main: selling.py, xmins_sell/ boosters, the shadow block in build.py, tools/score_shadow.py and validate.py checks.
  One change from #29: the `xmins_combine` switch was deleted in FL-116, so the shadow uses main's rule (bench chance
  capped at 1 − start chance).
- Live projections unchanged: two builds of the same data (main and branch) give identical players and plans (0 of
  472 players differ); test_xmins_sell_shadow checks the live xP is the same with or without the selling table.
- First shadow saved for GW11 (672 players with a fixture, 0 with missing selling inputs). Cost: one element-summary
  call per player once per transfer window (672 calls, about 17 s).
- Decision rule (agreed 31 Oct, unchanged): switch xmins_sell on only if, pooled over the shadow weeks, start-chance
  Brier is lower and xP MAE is no worse, with the paired bootstrap CI over GWs of the Brier difference below 0.
  Merged before the GW11 deadline (21 Nov), GW11-14 are scored once GW14 finishes (about 7 Dec), before GW15's
  deadline (12 Dec).
## 13 Nov 2026 — FL-068: backtests without hindsight (test only; live model unchanged)

- Known error (model log 23 Oct, "possible leak left: use_out"; FL-068 traced fplmodel L663, L587, L265): the backtest
  judged past forecasts with today's knowledge in three places. Fixed behind `hist_honest` (backtests only, on):
  - weeks out in the minutes history came from today's FPL notes (ctx["out"]): `known_out` rebuilds them from the
    status log and history/news.json as they stood at each deadline. By GW10 today's notes excused 39 past player-weeks
    the logs couldn't back at the time (1 the other way);
  - a player 'unavailable' today was zeroed in every past week; now only a flag saved at that deadline rules him out;
  - past xG went to today's club (17 summer movers, 0.98 xG in GW1-2); `clubs_then` credits it to the club he played
    for that week (from the live data's fixture ids; 0 ambiguous player-weeks).
- Penalty order can't be rebuilt: FPL keeps only the current order and history/setpieces.json starts 12 Nov with no
  changes. Measured instead: with no penalty bonus at all the backtest moves MAE −0.002 (status log) / −0.002 (none),
  so today's order flatters it by no more than that. Understat: 11 of this season's 15 penalties were taken by today's
  #1, 4 not (Le Fée ×3, Flemming, McGinn), so the order did change.
- How much hindsight flattered it (GW3-10, n=3050, honest − old):
  - no status log: MAE 1.812 → 1.824 (+0.012), corr 0.430 → 0.428; flagged players MAE +0.165 (n=202): the old
    run, meant to know no injuries, still knew today's;
  - status log (as live): MAE 1.763 → 1.765 (+0.002), corr 0.4440 → 0.4437; returning players' xMin MAE
    13.1 → 10.3 (n=120); no segment past the limits.
  - bench.py: this season MAE 1.763 → 1.765, picks 4.35 both, 5-GW picks 18.11 both; 2025/26 and 2024/25
    identical (no flags or news in the archive; club per week already from the archive). Every paired CI [0, 0].
- From now on model changes are judged on the honest backtest (FL-031, FL-067, FL-079 branch from this).

## 12 Nov 2026 — FL-074: plans with four from one club (planner; Adopt as Marginal)

- Known error (code review, reproduced 5 Nov): optimise.py and plan-solver.js capped every club at 3 in every plan
  week. A real move between Premier League clubs can leave a squad holding four from one club; then even keeping the
  squad broke the cap, so there were no plans in the build and Re-plan failed.
- Rule confirmed: FPL's limit is 3 (bootstrap-static `game_settings.squad_team_limit`); a manager left with four can
  keep them but "won't be able to make another transfer" until back to 3 (FPL, quoted by FourFourTwo on Solanke's move
  to Spurs). Fix: the extra player may stay in a week with no transfer; any week with a transfer ends with at most 3
  from every club. validate.py checks plans against that and warns while the squad holds more than 3.
- Projections unchanged: backtest and bench identical to main (every paired CI [0, 0]); `--compare` flags nothing.
- strategy_replay.py `--pick app`: identical to main except Chase rank 2025/26 (1855 → 1818). That run diverged at
  GW8 on a solve that hit its 20 s time limit while five replays shared four cores; with no club above 3 the change adds
  no constraint, so the maths is the same there. Read it as solver-timing noise, not an effect.
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal.
## 12 Nov 2026 — FL-073: Roll plans follow the profit rule (planner; Adopt as Marginal)

- Known error (code review, reproduced 5 Nov): optimise.strategy_plans exempted the Roll option from "no moves for the
  sake of it", so a Roll plan could recommend later transfers worth less than MIN_PROFIT (Chase rank −0.8 against doing
  nothing). Fix: a Roll plan whose moves miss MIN_PROFIT against keeping the squad is replaced by the keep-squad plan,
  with a note; validate.py no longer exempts Roll.
- Projections unchanged: backtest (GW3–10, n=3,050) MAE 1.812 / 1.763 with the status log, identical; `--compare`
  flags nothing; bench identical on all three seasons (5-GW picks 18.11 / 19.13 / 19.01), every paired CI [0, 0].
- strategy_replay.py `--pick app` (new: every move option the build offers, then the plan the app recommends), GW5–38:
  2025/26 Balanced 1790 → 1790, Play safe 1842 → 1839 (one week, GW5), Chase 1855 → 1855; 2024/25 all identical
  (2057 / 2082 / 1983). The rule bound once in 204 strategy-weeks.
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal.
## 12 Nov 2026 — FL-110: "no moves for the sake of it" measured against rolling (planner; Adopt as Marginal)

- Known error (audit 10 Nov, A5): the MIN_PROFIT rule compared a plan with never transferring for 5 GWs, which a
  Roll plan with later moves beats easily, so it hardly bound (live: Balanced 3 moves for +0.32 against rolling); the
  real guard was an undocumented 0.5 in the browser. CLAUDE.md's rule weighs the plan against rolling the free
  transfer. Fix: moves this week must beat the same strategy's Roll plan by MIN_PROFIT (else the option is dropped);
  the recommended margin (optimise.RECOMMEND_MARGIN, FL-108) is MIN_PROFIT; Re-plan applies the same check.
- Projections unchanged: backtest and bench identical to main, every paired CI [0, 0]; `--compare` flags nothing.
- strategy_replay.py `--pick app` (the plan the app recommends), GW5–38, FL-073 → FL-110, real points:
  2025/26 Balanced 1790 → 1849, Safe 1839 → 1889, Chase 1855 → 1824; 2024/25 2057 → 2068, 2082 → 2123,
  1983 → 2118 (sum +265 over six runs). Projected points move the other way in 2024/25 (−6.9, −5.2, −12.4) and sum
  −4.8, so read the real-points gain as mostly path noise. Default replay (`--pick best`), main → FL-110: +103, −151,
  +56, +2, +83, −57 real (+36). Several runs diverge on solves that hit the 20 s limit under load.
- Live GW11: every move-now option is within +0.2 of rolling, so only the Roll plans are published.
- Decision: CI includes zero, fixes a known error (rule measured against the wrong yardstick; undocumented
  threshold), no segment worse → Adopt as Marginal. Arguable: if the yardstick is read as a threshold choice (a
  tweak), the row is "Don't adopt". Re-check the replay without CPU contention.
## 12 Nov 2026 — FL-116: dead code removed (neutral, as required)

- Removed the rejected minutes switches `p60_prior` / `mstart_prior` (22 Oct: worse on both seasons at every weight)
  and `xmins_combine`'s "A" path (more bias); both were off, so the remaining maths is the same expression with zero
  weights. `start_prior` stays (left at 0 deliberately; a candidate for returning regulars, see FL-093).
- Backtest JSON with and without the status log byte-identical to main `a8f877b`; bench identical on all three seasons
  (1-GW MAE 1.763 / 1.858 / 1.763, 5-GW picks 18.18 / 19.13 / 19.01, every paired CI [0, 0]).
- One-off tuning scripts (tune.py, tune_v3.py, tune_odds.py) are gone; bench.py does the same comparisons
  (`python3 bench.py '{"sp_match": 0.5}'`). tune_ep.py stays for FL-134.
## 12 Nov 2026 — FL-113: priors from the last two calendar seasons only (Adopt as Marginal)

- Known error (audit B8 / N6): make_priors.py took a player's last two Premier League seasons however old (42 of 481
  priors on 9 Nov predated 2025/26, back to 2015/16; FPL xG is 0 before 2022/23), while archive.py, which builds the
  backtests' past-season priors, already used the two calendar seasons before. Failed downloads shrank the file silently.
- Fix: priors only from the two seasons before the current one (2024/25, 2025/26), weights 1:2, zero-minute seasons left
  out (as archive.py); never a season before 2022/23; the script exits 1 and keeps the old file if more than 2% of
  downloads fail or the count drops below 85% of the previous file. priors.json records its "seasons"; validate.py
  errors on a prior from another season.
- Same download (12 Nov) through old and new logic: 481 → 459 priors (22 dropped: older seasons or 0 minutes in both
  recent seasons), 72 changed. priors.json in this PR is the new-logic file.
- Backtest (GW3–10, n=3,050), old-logic v new-logic priors: without status log MAE 1.8111 → 1.8120, corr .4301 → .4301;
  with 1.7625 → 1.7634, .4439 → .4440. No flags. "Has prior" +0.020 MAE / "no prior" −0.019 to −0.022 (players moved
  between the two). Top 30: −0.010 / +0.006.
- bench.py: past seasons identical (archive.py already used this rule; CIs [0, 0]). This season: 1-GW MAE 1.7625 →
  1.7634, picks 4.353 → 4.347 (−0.006 [−0.083, +0.061]); 5-GW picks 18.18 → 18.11 (−0.07 [−0.20, 0.00], 4 origins);
  captain unchanged 0/8.
- Live GW11: 13 players move more than 0.1 xP over 5 GWs (Egan +1.26, Ajayi +0.83, Tzolis +0.49, N.Jackson −0.35).
- Decision: CI includes zero, fixes a known error, no segment worse → Adopt as Marginal. Re-check this season's
  5-GW picks around GW20, when there are enough origins.
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
(Entry added 11 Nov 2026 from `docs/archive/xmins-eval.md` and the comment on `DEFAULTS["xmins"]` in fplmodel.py; no new runs.)
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

## 23 Oct 2026 — stress test (branch `stress-test`, tests only; report archived at `docs/archive/stress-test-report-2026-10-23.md`)
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
