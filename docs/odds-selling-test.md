# Player odds and late-selling minutes: first tests (31 Oct 2026)

Research only, nothing merged. Scripts: scratchpad /tmp/claude-0/odds5 and /tmp/claude-0/xmins6 (session-only).

## Idea 5: player goal/assist odds (GW8 only: 10 fixtures, 426 players priced)
- Goals, 1+ (Brier, played pool n=265, 14 goals): model .0458, market (de-margined to team goals) .0494, diff +.0036 [+.0006, +.0067]. Likely starters (n=124): level (+.0007, CI spans 0). Blends add nothing.
- Points (played pool): xP corr 0.272 -> 0.262 and MAE 1.951 -> 1.985 at full market weight; worse at every weight.
- Assists, 1+: market ranks better (AUC .706 vs .622); after rescaling to the model's team totals, Brier -.0022 [-.0045, -.0001] (n=208, 15 assists).
- Verdict: goals Coin flip, assists Marginal. Re-test after ~5 more GWs.
- Collection bugs found: p_assist still carries the bookmaker margin (mean .161 vs real ~.07); only the last (3 h) snapshot per GW is kept, so 72 h / 24 h are lost; unmatched names are overwritten each run; keepers never priced.
- GW9 disagreements to check (model vs market P(goal)): Barry .341/.194, McBurnie .308/.167, Raul Jimenez .268/.158, Rogers .143/.246, Evanilson .276/.174, Thiago .350/.256, N.Jackson .301/.230, Rudoni .180/.112, Calvert-Lewin .270/.203, Neto .125/.190.

## Idea 6: xMins retrained with late-selling features
- S = shipped boosters, A = retrain on the same 21 features, B = A + sell_share, sell_spike, log ownership. Two folds (test 2025/26; test 2024/25). Archive transfers for GW k confirmed pre-deadline.
- Start Brier, all rows: 2025/26 .079 / .076 / .072 (B-A -.004 [-.005, -.003]); 2024/25 .089 / .085 / .081 (-.003 [-.004, -.002]).
- Likely starters with 8%+ selling: start Brier .210 -> .153 (2025/26), .224 -> .165 (2024/25). Real start rate ~.72-.74; B predicts ~.75, S/A ~.89.
- Points (bench, A -> B): 2025/26 corr .413 -> .427, rank .509 -> .533, MAE 1.866 -> 1.847; 2024/25 corr .428 -> .440, rank .512 -> .532, MAE 1.772 -> 1.750. 1-GW picks/captain/top-5 CIs span 0. 5-GW picks +0.34 [+0.11, +0.61] and +0.28 [+0.02, +0.52]; 5-GW corr 2024/25 -0.011 (selling signal wrongly applied to all 5 weeks).
- Current season with real flags (GW4-8): start Brier B-A -.0019 [-.0036, +.0001]; unflagged likely starters with 8%+ selling -.021 [-.035, -.014], n 126. Flags already capture about half the archive gain.
- Live data: element-summary/{id} history gives per-round transfers and `selected` for this season, so the spike baseline exists now; no need to wait 6 GWs. The live transfer log's `owned` is selected-by-percent x10 and it lacks total managers; take pre-window ownership from element-summary instead.
- Verdict: Strong that it is worth building (as shadow first), Marginal on size of live gain. Apply the selling signal to the next GW only.
