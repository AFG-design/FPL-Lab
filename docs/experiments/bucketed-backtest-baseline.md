# Bucketed backtest baseline (`--bucketed`)

Date: 20 November 2026. Baseline commit on `main`: `5fafb87` (default `fplmodel.DEFAULTS`, no parameter overrides).

Command:

```sh
python3 backtest.py --bucketed
```

## Setup and scope

- **Seasons:** `2024-25` and `2025-26`, GW4–38 (35 gameweeks each; 70 pooled). Each season is evaluated independently from its own observations, and pooled rows aggregate the raw observations across both seasons.
- **No hindsight:** every GW `k` is projected strictly from data before `k` (`horizon=1`, `use_flags=False`), with archive betting odds (`odds/archive/2024-25.json` and `odds/archive/2025-26.json`, 380/380 fixtures each) and historical European congestion (`europe_hist.json`), matching `bench.py`.
- **Populations:**
  - **Minutes** and **Goals & assists:** a-priori pool (played in at least one of the previous 3 GWs), single-fixture weeks only (doubles sum stats across two matches).
  - **Clean sheets:** Team CS covers all finished team-fixtures in GW4–38 (`350 × 2 = 700` per season); Player CS covers single-fixture pool players in CS-scoring positions (GKP, DEF, MID).
  - **Total xP:** all a-priori pool player-weeks in GW4–38 (including doubles). Top-50 Spearman is the mean per-GW Spearman rank correlation of the top 50 projected pool players (ties on predicted xP broken deterministically by player ID, never actual points).
- **Calibration / bias sign:** `pred - act` (positive = model over-projects, negative = model under-projects).

## 1. Minutes

| Season | n | `>0` Brier | `>0` cal (`pred − act`) | `>=60` Brier | `>=60` cal (`pred − act`) | xMin MAE | xMin RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-25 | 12,814 | 0.1434 | +0.0710 | 0.1632 | −0.0085 | 22.67 | 29.64 |
| 2025-26 | 12,657 | 0.1405 | +0.0703 | 0.1564 | −0.0094 | 22.35 | 29.24 |
| **Pooled** | **25,471** | **0.1420** | **+0.0707** | **0.1598** | **−0.0090** | **22.51** | **29.44** |

## 2. Clean sheets

| Season | Team n | Team Brier | Team log-loss | Player n | Player Brier | Player log-loss |
|---|---:|---:|---:|---:|---:|---:|
| 2024-25 | 700 | 0.1749 | 0.5288 | 11,440 | 0.1143 | 0.3889 |
| 2025-26 | 700 | 0.1746 | 0.5284 | 11,121 | 0.1179 | 0.4016 |
| **Pooled** | **1,400** | **0.1748** | **0.5286** | **22,561** | **0.1161** | **0.3952** |

## 3. Goals & assists (expected vs actual counts)

| Season | n | Goals RMSE | Goals MAE | Assists RMSE | Assists MAE | G+A RMSE | G+A MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-25 | 12,814 | 0.2713 | 0.1205 | 0.2628 | 0.1135 | 0.3862 | 0.2120 |
| 2025-26 | 12,657 | 0.2724 | 0.1190 | 0.2558 | 0.1105 | 0.3773 | 0.2096 |
| **Pooled** | **25,471** | **0.2718** | **0.1197** | **0.2594** | **0.1120** | **0.3818** | **0.2108** |

## 4. Total xP

| Season | n | GWs | RMSE | MAE | Bias (`pred − act`) | Top-50 Spearman |
|---|---:|---:|---:|---:|---:|---:|
| 2024-25 | 13,003 | 35 | 2.6117 | 1.7600 | +0.0117 | 0.1948 |
| 2025-26 | 12,847 | 35 | 2.7131 | 1.8676 | −0.0206 | 0.1053 |
| **Pooled** | **25,850** | **70** | **2.6626** | **1.8135** | **−0.0043** | **0.1501** |

## Key baseline observations

- **`P(mins > 0)` is over-estimated by ~7.1 percentage points in both seasons** (`+0.0710` in 2024-25, `+0.0703` in 2025-26, `+0.0707` pooled), whereas `P(mins >= 60)` is close to calibrated (`−0.0085` / `−0.0094`).
- **Top-50 Spearman differs markedly between seasons** (`0.1948` in 2024-25 vs `0.1053` in 2025-26), reinforcing why per-season figures must always be reported alongside pooled numbers.
