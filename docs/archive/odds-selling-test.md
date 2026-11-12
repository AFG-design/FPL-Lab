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


## FL-091: collection contract for the GW12–13 re-test

The collector already separated raw assist prices and introduced checkpoint storage in #30. FL-091 makes those
checkpoints write-once (including forced runs), accumulates unmatched names and skips known keepers. It does not
change the model or goal-odds storage: `p_score` remains the median implied chance, with margin still included.

New history files retain the latest-snapshot aliases used by Health and older research readers:

```json
{
  "gw": 11,
  "deadline": "2026-11-21T11:00:00Z",
  "regions": "us",
  "built": "latest snapshot timestamp",
  "fixtures": {"fixture id": {"players": {"player id": {"p_score": 0.25, "p_assist_raw": 0.2}}}},
  "unmatched_players": ["deduplicated names seen during this GW"],
  "unmatched_teams": [],
  "snapshots": {
    "72": {"built": "timestamp", "credits_used": 20, "fixtures": {}, "unmatched_players": [], "unmatched_teams": []},
    "24": {"built": "timestamp", "credits_used": 20, "fixtures": {}, "unmatched_players": [], "unmatched_teams": []},
    "3": {"built": "timestamp", "credits_used": 20, "fixtures": {}, "unmatched_players": [], "unmatched_teams": []}
  }
}
```

Each snapshot has its own fixture/player rows and that run's unmatched names. The top-level history lists are the
union for that GW; `odds/players.json` accumulates names across GWs and continues to expose the latest fixtures for
Health. `p_assist_raw` is the median Over implied probability, still including margin. `p_assist` is saved only when
Over and Under are both priced by the same bookmaker, with `assist_pairs` recording the number of pairs. Over-only
prices are never labelled fair. No bookmaker prices are stored.

Use `odds_players.snapshots(odds_players.load_json(path))` to read history. Old single-snapshot files become one
`legacy` snapshot **in memory only**; their unknown checkpoint is not guessed. GW8–9's old `p_assist` mixes raw and
fair probabilities, so it cannot be treated as clean fair odds or reconstructed raw prices. The scratch rescaling
scripts use `p_assist_raw` when present and explicitly treat the old field as margin-bearing otherwise. The GW8
check selects `legacy` or the `3` checkpoint explicitly; it fails if that checkpoint is missing. Existing GW8–10
files are not rewritten. The session-only scratchpads mentioned above are not repository files.

Missing key: skip collection. Missing/unreadable history: a missing file starts a new GW; malformed existing JSON
fails visibly rather than being replaced. No priced outfield players: report an error for Health, leave the key
unsaved and allow a retry. Partial coverage is kept as observed, never filled with later prices. A missed checkpoint
is not backdated: the current checkpoint is saved, and validation warns about missing keys after the deadline.
Forced runs cannot collect after the deadline or overwrite a key. An explicitly forced pre-72 h run has its own
write-once `early` key.

Credits: **10 fixtures × 2 markets × 1 region × 3 checkpoints = about 60 per GW**, or 240–300 for four/five GWs.
Event listing is free; keeper filtering does not reduce event-market charges. Only one region is allowed. Paid
requests stop before spending the 40-credit reserve, and missing remaining-credit headers stop further paid
requests. Duplicate checkpoints spend zero. Double GWs, retries with no prices, or a forced `early` run cost extra
(two credits per fetched fixture); the remaining-credit guard still bounds use within the free 500-credit quota.

Regression coverage uses a fake clock and API: all three checkpoints survive, repeat/forced runs leave existing
history byte-for-byte unchanged, names accumulate without duplicates, GW8 loads without rewriting, keepers are
omitted, raw/fair assists stay separate, goal odds stay unchanged, and budget/late-run/error guards are checked.
