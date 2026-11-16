# FL-162: minutes retraining protocol

Declared before training or evaluation, 16 November 2026. Stacked on FL-163 for its
report-only regular-player pool. The current model and xmins_sell shadow stay separate.

Two variants, with all results reported:

1. **Retrained**: retrain all four conditional minutes boosters together, using the
   existing 21 xMins inputs and fixed hyperparameters from train_xmins_sell.py:
   320 rounds, eta 0.05, depth 4, min_child_weight 5, subsample/colsample 0.8,
   lambda 1, seed 0. The four targets jointly determine expected minutes, so they
   are one linked minutes package, targeting start chance and minutes accuracy.
2. **Recalibrated**: the same retrained package with a logistic intercept/slope
   recalibration of start chance. Fit calibration only on the preceding season's
   out-of-sample predictions, from a model trained strictly before that season.
   Fix the calibration method before examining any test-season result; no bin tuning.

Walk-forward: train on 2022/23–2023/24, test 2024/25; add 2024/25 training,
then test 2025/26; add 2025/26 training, then test the current season. Calibration
for 2024/25 uses 2023/24 predictions trained on 2022/23 only. No test-season rows
train its boosters or calibrator. The original training recipe was not supplied;
this is a reproducible reconstruction, not an exact reproduction of the original fit.

Evaluate the shipped model alongside both variants. Report start Brier, 60+ Brier,
xMin RMSE, reliability by fixed ten-percentage-point bins, existing and FL-163
pools, 1-/5-GW picks, paired intervals, pooled past-season start loss and picks,
and backtest segments with and without the status log. Apply CLAUDE.md's targeted
change / no-harm rules. The current season does not decide. Do not promote a model
merely because its training data are newer. Keep or reject each variant explicitly.

Training writes plain JSON experiment boosters outside xmins/. Missing sources,
empty conditional targets or failed calibration raise. Do not overwrite history/.
