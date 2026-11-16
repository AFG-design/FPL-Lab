# FL-162: walk-forward minutes experiment

Date: 16 November 2026. Protocol was committed and PR #187 opened before training. Depends on FL-163 (PR #186).

**Decision: do not adopt either variant.** Both trip the current-season top-30 MAE guard rail with and without deadline flags. Retraining also trips the correlation no-harm check in 2024/25. The shipped model files and the xmins_sell shadow are unchanged. This PR retains reproducible tooling and the complete results, not a projection change.

Four conditional models form one linked minutes package. Fixed 21 inputs; 320 rounds, depth 4, eta 0.05, seed 0, remaining parameters from `tools/train_xmins_sell.py`. Training runs cumulatively from 2022/23 through the season immediately before the evaluation season. The 2024/25 retrain uses the same seasons as the original; it controls for reconstructing the unavailable original recipe. Later folds add newer seasons.

Recalibration uses ridge-logistic intercept/slope fitting on the immediately previous season’s out-of-sample predictions (that calibration model was trained strictly before that season). No test-season training, calibration, early stopping or parameter selection. The current season is reported, but does not decide.

Run from the repository root with the requirements installed and `raw/` populated:

```sh
python tools/retrain_minutes.py train --out /tmp/fl162
python tools/retrain_minutes.py evaluate --out /tmp/fl162
python tools/retrain_minutes.py backtest --out /tmp/fl162
```

Candidates and full JSON outputs are written outside the repository. Missing source labels, conditional targets or calibration classes fail loudly. Feature history excludes the target and future gameweeks, keeps prior-club minutes, and represents unknown features as NaN. Doubles repeat the deadline vector for each fixture; direct minutes scoring uses only single-fixture weeks.

## Minutes accuracy

Lower is better. Each model is scored on the same player-weeks within a pool. Differences between pools are population differences, not model gains.

| Season | Pool | Variant | n | Start Brier | 60+ Brier | xMin RMSE | xMin MAE |
|---|---|---|---:|---:|---:|---:|---:|
| 2024-25 | pool | shipped | 12814 | 0.14853 | 0.16317 | 29.641 | 22.673 |
| 2024-25 | pool | retrained | 12814 | 0.14966 | 0.16442 | 29.717 | 22.612 |
| 2024-25 | pool | recalibrated | 12814 | 0.16901 | 0.17563 | 31.880 | 26.155 |
| 2024-25 | regular | shipped | 14355 | 0.13724 | 0.15014 | 28.599 | 21.112 |
| 2024-25 | regular | retrained | 14355 | 0.13826 | 0.15126 | 28.668 | 21.065 |
| 2024-25 | regular | recalibrated | 14355 | 0.15887 | 0.16332 | 31.050 | 25.258 |
| 2025-26 | pool | shipped | 12657 | 0.14499 | 0.15648 | 29.240 | 22.293 |
| 2025-26 | pool | retrained | 12657 | 0.14471 | 0.15632 | 29.203 | 22.248 |
| 2025-26 | pool | recalibrated | 12657 | 0.14494 | 0.15634 | 29.295 | 22.703 |
| 2025-26 | regular | shipped | 14243 | 0.13525 | 0.14492 | 28.350 | 20.838 |
| 2025-26 | regular | retrained | 14243 | 0.13499 | 0.14476 | 28.315 | 20.794 |
| 2025-26 | regular | recalibrated | 14243 | 0.13518 | 0.14478 | 28.401 | 21.274 |
| current | pool | shipped | 3050 | 0.11669 | 0.13367 | 25.969 | 19.054 |
| current | pool | retrained | 3050 | 0.11742 | 0.13449 | 25.840 | 18.819 |
| current | pool | recalibrated | 3050 | 0.11710 | 0.13436 | 25.855 | 18.922 |
| current | regular | shipped | 3344 | 0.11012 | 0.12510 | 25.345 | 17.906 |
| current | regular | retrained | 3344 | 0.11086 | 0.12590 | 25.233 | 17.689 |
| current | regular | recalibrated | 3344 | 0.11053 | 0.12575 | 25.241 | 17.786 |

## Bench totals and per-season intervals

`pool` is the existing deciding pool. `regular` is FL-163’s second pool, report only. 1-GW picks are real points per selected player; 5-GW picks are the corresponding five-week total. Intervals are candidate minus shipped, paired bootstrap over gameweeks/origins.

| Season | Variant | Pool 1-GW picks | Pool 5-GW picks | 5-GW difference [95% CI] | Regular 1-GW picks | Regular 5-GW picks |
|---|---|---:|---:|---|---:|---:|
| 2024-25 | shipped | 4.2495 | 19.1644 | reference | 4.2495 | 19.1644 |
| 2024-25 | retrained | 4.2470 | 19.1141 | -0.050 [-0.169, +0.064] | 4.2470 | 19.1141 |
| 2024-25 | recalibrated | 4.1917 | 19.0333 | -0.131 [-0.281, +0.028] | 4.1905 | 19.0333 |
| 2025-26 | shipped | 4.4413 | 19.1267 | reference | 4.4413 | 19.1267 |
| 2025-26 | retrained | 4.4616 | 19.1207 | -0.006 [-0.125, +0.108] | 4.4616 | 19.1207 |
| 2025-26 | recalibrated | 4.4559 | 19.1719 | +0.045 [-0.089, +0.179] | 4.4559 | 19.1719 |
| current | shipped | 4.3639 | 18.2389 | reference | 4.3639 | 18.2389 |
| current | retrained | 4.4861 | 18.3111 | +0.072 [-0.278, +0.339] | 4.4861 | 18.3111 |
| current | recalibrated | 4.4750 | 18.3000 | +0.061 [-0.311, +0.339] | 4.4750 | 18.3000 |

### No-harm checks

| Season | Variant | 1-GW picks CI | Captain CI | Top-five CI | Correlation CI |
|---|---|---|---|---|---|
| 2024-25 | retrained | -0.0025 [-0.0463, +0.0381] | -0.2286 [-0.6857, +0.0000] | -0.1657 [-0.4000, +0.0000] | -0.001221 [-0.002388, -0.000059] |
| 2024-25 | recalibrated | -0.0578 [-0.1213, +0.0070] | +0.2571 [-0.4571, +1.4571] | -0.1486 [-0.3943, +0.0000] | -0.004037 [-0.009367, +0.001303] |
| 2025-26 | retrained | +0.0203 [-0.0298, +0.0698] | +0.2286 [-0.3143, +0.9143] | +0.0400 [-0.2057, +0.2629] | +0.001428 [-0.000160, +0.003083] |
| 2025-26 | recalibrated | +0.0146 [-0.0349, +0.0654] | +0.2857 [-0.2571, +0.9429] | +0.0457 [-0.2000, +0.2686] | +0.001281 [-0.000621, +0.003206] |
| current | retrained | +0.1222 [+0.0639, +0.1861] | -1.1250 [-3.3750, +0.0000] | +0.0000 [+0.0000, +0.0000] | +0.002466 [-0.000534, +0.004497] |
| current | recalibrated | +0.1111 [+0.0528, +0.1750] | -1.1250 [-3.3750, +0.0000] | +0.0000 [+0.0000, +0.0000] | +0.002203 [-0.000902, +0.004370] |

## Pooled past seasons

Both past seasons resampled within season, then pooled. Negative part loss differences are better; positive picks differences are better.

| Pool | Variant | 5-GW picks difference [95% CI] | Start-loss difference [95% CI] |
|---|---|---|---|
| deciding | retrained | -0.028148 [-0.109630, +0.051852] | +0.000428 [-0.000145, +0.000970] |
| deciding | recalibrated | -0.042963 [-0.147037, +0.060000] | +0.010275 [+0.008964, +0.011623] |
| regular (report only) | retrained | -0.028148 [-0.109630, +0.051852] | +0.000383 [-0.000127, +0.000863] |
| regular (report only) | recalibrated | -0.042963 [-0.147037, +0.060000] | +0.010822 [+0.009597, +0.012031] |

### All pooled scoring parts (deciding pool)

| Part | Retrained loss difference [95% CI] | Recalibrated loss difference [95% CI] |
|---|---|---|
| cs | +0.000352 [-0.000411, +0.001160] | +0.001645 [+0.000204, +0.003066] |
| start | +0.000428 [-0.000145, +0.000970] | +0.010275 [+0.008964, +0.011623] |
| p60 | +0.000551 [+0.000152, +0.000970] | +0.006200 [+0.005331, +0.007078] |
| goals | -0.000068 [-0.000519, +0.000372] | +0.002827 [+0.001576, +0.004089] |
| assists | -0.000441 [-0.000892, -0.000024] | +0.001730 [+0.000166, +0.003212] |
| dc | -0.000006 [-0.000065, +0.000041] | +0.000005 [-0.000070, +0.000065] |
| bonus | -0.000095 [-0.000238, +0.000043] | +0.000442 [+0.000115, +0.000753] |
| saves | +0.000668 [-0.000523, +0.001752] | +0.005173 [+0.002012, +0.008467] |

## Current-season segment checks

| Flags | Variant | MAE before → after | Correlation before → after | Flagged segment | ΔMAE | Δbias |
|---|---|---|---|---|---:|---:|
| none | retrained | 1.8220 → 1.8123 | 0.4280 → 0.4308 | Top 30 projected: top 30 each GW (n=240) | +0.07311 | -0.05688 |
| none | recalibrated | 1.8220 → 1.8198 | 0.4280 → 0.4304 | Top 30 projected: top 30 each GW (n=240) | +0.05012 | -0.04684 |
| deadline log | retrained | 1.7629 → 1.7548 | 0.4439 → 0.4463 | Top 30 projected: top 30 each GW (n=240) | +0.12785 | -0.15238 |
| deadline log | recalibrated | 1.7629 → 1.7609 | 0.4439 → 0.4461 | Top 30 projected: top 30 each GW (n=240) | +0.08912 | -0.10482 |

Decision-table row for both variants: **Any segment trips `--compare`: do not adopt until fixed or explained.** The regressions remain unexplained, so there is no exception or promotion. No additional variants were tried.

## Start-chance reliability

Fixed bins [0,10), …, [90,100]. Each cell is **n; mean predicted → actual starts**. Empty bins are shown as a dash. These use the app’s final start chance (after its existing adjustments), not training predictions.

### 2024-25, pool

| Start-chance bin | Shipped | Retrained | Recalibrated |
|---|---|---|---|
| 0-10% | 1324; 6.1% → 7.6% | 1465; 5.7% → 8.7% | — |
| 10-20% | 1541; 14.7% → 15.8% | 1522; 14.6% → 18.1% | 182; 16.1% → 2.7% |
| 20-30% | 963; 24.8% → 29.2% | 906; 24.5% → 29.2% | 706; 25.8% → 6.2% |
| 30-40% | 839; 34.9% → 37.9% | 688; 35.1% → 34.3% | 1173; 35.4% → 15.5% |
| 40-50% | 743; 44.9% → 44.7% | 727; 45.0% → 46.2% | 1382; 44.9% → 21.5% |
| 50-60% | 773; 55.1% → 59.2% | 797; 55.1% → 57.3% | 1153; 55.1% → 33.3% |
| 60-70% | 838; 65.4% → 64.8% | 784; 65.3% → 63.4% | 1465; 65.3% → 51.8% |
| 70-80% | 1264; 75.4% → 74.4% | 1291; 75.6% → 72.8% | 2060; 75.6% → 69.2% |
| 80-90% | 2306; 85.6% → 86.2% | 2300; 85.5% → 85.8% | 3643; 85.2% → 87.6% |
| 90-100% | 2223; 93.2% → 93.6% | 2334; 93.5% → 93.3% | 1050; 90.9% → 94.9% |

### 2024-25, regular

| Start-chance bin | Shipped | Retrained | Recalibrated |
|---|---|---|---|
| 0-10% | 2599; 4.3% → 5.5% | 2719; 4.1% → 6.1% | 602; 6.7% → 0.8% |
| 10-20% | 1791; 14.6% → 15.1% | 1790; 14.5% → 17.0% | 482; 14.6% → 2.7% |
| 20-30% | 979; 24.8% → 29.0% | 925; 24.4% → 29.2% | 883; 25.7% → 6.8% |
| 30-40% | 839; 34.9% → 37.9% | 688; 35.1% → 34.3% | 1484; 35.4% → 14.0% |
| 40-50% | 743; 44.9% → 44.7% | 727; 45.0% → 46.2% | 1529; 44.8% → 20.5% |
| 50-60% | 773; 55.1% → 59.2% | 797; 55.1% → 57.3% | 1157; 55.1% → 33.3% |
| 60-70% | 838; 65.4% → 64.8% | 784; 65.3% → 63.4% | 1465; 65.3% → 51.8% |
| 70-80% | 1264; 75.4% → 74.4% | 1291; 75.6% → 72.8% | 2060; 75.6% → 69.2% |
| 80-90% | 2306; 85.6% → 86.2% | 2300; 85.5% → 85.8% | 3643; 85.2% → 87.6% |
| 90-100% | 2223; 93.2% → 93.6% | 2334; 93.5% → 93.3% | 1050; 90.9% → 94.9% |

### 2025-26, pool

| Start-chance bin | Shipped | Retrained | Recalibrated |
|---|---|---|---|
| 0-10% | 1197; 6.1% → 7.8% | 1209; 5.8% → 7.7% | 862; 6.3% → 5.5% |
| 10-20% | 1519; 14.7% → 16.3% | 1469; 14.7% → 17.2% | 1409; 15.0% → 15.7% |
| 20-30% | 1007; 24.7% → 22.8% | 1001; 24.6% → 21.6% | 1130; 24.8% → 20.1% |
| 30-40% | 775; 34.9% → 40.1% | 729; 34.9% → 36.6% | 805; 34.8% → 30.1% |
| 40-50% | 793; 44.8% → 47.7% | 710; 45.0% → 47.0% | 755; 45.0% → 46.4% |
| 50-60% | 704; 55.0% → 53.0% | 812; 55.0% → 53.4% | 860; 55.0% → 52.3% |
| 60-70% | 849; 65.3% → 65.0% | 883; 65.3% → 63.6% | 983; 65.2% → 62.6% |
| 70-80% | 1211; 75.3% → 77.1% | 1221; 75.4% → 76.5% | 1314; 75.3% → 77.0% |
| 80-90% | 2174; 85.5% → 87.1% | 2121; 85.8% → 87.1% | 2356; 85.7% → 87.7% |
| 90-100% | 2428; 93.2% → 93.1% | 2502; 93.5% → 93.2% | 2183; 93.0% → 93.4% |

### 2025-26, regular

| Start-chance bin | Shipped | Retrained | Recalibrated |
|---|---|---|---|
| 0-10% | 2478; 4.1% → 6.2% | 2499; 4.0% → 6.3% | 2040; 4.0% → 4.5% |
| 10-20% | 1808; 14.5% → 15.7% | 1747; 14.5% → 16.4% | 1774; 14.9% → 15.1% |
| 20-30% | 1023; 24.7% → 22.9% | 1018; 24.6% → 21.5% | 1171; 24.7% → 20.2% |
| 30-40% | 775; 34.9% → 40.1% | 730; 34.9% → 36.7% | 807; 34.8% → 30.1% |
| 40-50% | 793; 44.8% → 47.7% | 710; 45.0% → 47.0% | 755; 45.0% → 46.4% |
| 50-60% | 704; 55.0% → 53.0% | 812; 55.0% → 53.4% | 860; 55.0% → 52.3% |
| 60-70% | 849; 65.3% → 65.0% | 883; 65.3% → 63.6% | 983; 65.2% → 62.6% |
| 70-80% | 1211; 75.3% → 77.1% | 1221; 75.4% → 76.5% | 1314; 75.3% → 77.0% |
| 80-90% | 2174; 85.5% → 87.1% | 2121; 85.8% → 87.1% | 2356; 85.7% → 87.7% |
| 90-100% | 2428; 93.2% → 93.1% | 2502; 93.5% → 93.2% | 2183; 93.0% → 93.4% |

### current, pool

| Start-chance bin | Shipped | Retrained | Recalibrated |
|---|---|---|---|
| 0-10% | 478; 4.9% → 4.4% | 555; 4.6% → 5.6% | 520; 4.8% → 4.6% |
| 10-20% | 336; 14.3% → 12.5% | 368; 14.4% → 16.8% | 366; 14.6% → 16.1% |
| 20-30% | 204; 24.6% → 26.0% | 184; 23.9% → 29.9% | 207; 24.1% → 28.0% |
| 30-40% | 180; 34.7% → 36.7% | 108; 34.8% → 36.1% | 108; 35.0% → 40.7% |
| 40-50% | 148; 44.8% → 41.9% | 127; 45.2% → 44.9% | 126; 45.4% → 40.5% |
| 50-60% | 124; 55.1% → 65.3% | 148; 55.3% → 66.9% | 142; 55.1% → 61.3% |
| 60-70% | 178; 65.0% → 70.2% | 178; 65.7% → 68.0% | 182; 65.3% → 70.9% |
| 70-80% | 258; 75.3% → 82.6% | 258; 75.4% → 83.3% | 271; 75.3% → 82.3% |
| 80-90% | 512; 85.4% → 91.2% | 501; 85.5% → 90.4% | 510; 85.5% → 90.6% |
| 90-100% | 632; 93.6% → 94.1% | 623; 93.7% → 95.2% | 618; 93.7% → 95.1% |

### current, regular

| Start-chance bin | Shipped | Retrained | Recalibrated |
|---|---|---|---|
| 0-10% | 760; 3.4% → 4.1% | 841; 3.4% → 4.9% | 806; 3.5% → 4.2% |
| 10-20% | 348; 14.3% → 13.2% | 376; 14.4% → 17.6% | 374; 14.6% → 16.8% |
| 20-30% | 204; 24.6% → 26.0% | 184; 23.9% → 29.9% | 207; 24.1% → 28.0% |
| 30-40% | 180; 34.7% → 36.7% | 108; 34.8% → 36.1% | 108; 35.0% → 40.7% |
| 40-50% | 148; 44.8% → 41.9% | 127; 45.2% → 44.9% | 126; 45.4% → 40.5% |
| 50-60% | 124; 55.1% → 65.3% | 148; 55.3% → 66.9% | 142; 55.1% → 61.3% |
| 60-70% | 178; 65.0% → 70.2% | 178; 65.7% → 68.0% | 182; 65.3% → 70.9% |
| 70-80% | 258; 75.3% → 82.6% | 258; 75.4% → 83.3% | 271; 75.3% → 82.3% |
| 80-90% | 512; 85.4% → 91.2% | 501; 85.5% → 90.4% | 510; 85.5% → 90.6% |
| 90-100% | 632; 93.6% → 94.1% | 623; 93.7% → 95.2% | 618; 93.7% → 95.1% |

## Validation and limits

- Unit tests cover future-outcome invariance, double-fixture labels, temporal fold boundaries, probability-bin edges, calibration failure, isolated model overrides, output-path protection and paired CI identity.
- Full Python suite passes; no production model settings, boosters, history files or site code change.
- Original training implementation was not supplied. Retraining uses the app’s reconstructed features and the fixed existing local trainer recipe; an effect cannot be attributed solely to fresher data.
- Existing archive limitations remain: historical fixture schedules, end-of-season penalty order, and prices are reconstructed as documented in the existing backtest. There are no historical injury flags for past seasons.
- FL-163’s pool does not cover unseen arrivals or overseas newcomers without qualifying PL history. Do not claim universal new-player coverage.
- The diagnostic regular pool is not added to the deciding rule. FL-131’s selling-informed shadow remains untouched.
