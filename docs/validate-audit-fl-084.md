# FL-084 validator audit

Audit of every check in `validate.py`, 8 November 2026. This changes validation and its source evidence only; it does not change model results or existing warning severity.

## Added and repaired

| Check | Previously | Now / failing example |
| --- | --- | --- |
| Free Hit restore | Compared `squad_gw` with `picks_gw - 1`, both set by the same restore path; never compared players | Derives the required restore from FPL chip history and compares all 15 ids with FPL's pre-Free-Hit picks. A different squad fails even with consistent metadata. False restore flags, wrong source weeks, stale/wrong-entry or incomplete evidence fail too. |
| Free transfers | Unchecked | Integer 0–5; missing, fractional, negative, 6, boolean or non-finite values fail. |
| Bank | Unchecked | Finite and non-negative; missing, negative, boolean or non-finite values fail. |
| Selling prices | Unchecked | Buy/sell/current prices must be finite, non-negative £0.1m amounts. Sell cannot exceed current, and must equal purchase plus half the gain rounded down, or current after a fall. Integer tenths avoid floating-point floor errors. Missing players/prices fail. |
| Squad size | Empty list bypassed the guard | Empty, duplicate or non-15 squads fail after the first deadline. An empty pre-season squad is still allowed. |
| Season starts | Skipped if the player's optional detail row was missing; NaN could pass comparisons | Checks the main-file fields regardless of detail availability and rejects non-finite starts. |
| xP detail sum | Empty dict and NaN components bypassed the comparison | An empty/non-finite breakdown with positive next-GW xP fails, as does a wrong finite total. Missing detail retains the existing optional-data behaviour. |
| Review saved forecast | Existing snapshot ignored if `xi_proj` was null | A saved snapshot requires a finite projection and the snapshot source marker; null can no longer bypass the check. |
| Journal finished weeks | An explicitly empty list disabled the membership check | If `finished_gws` is supplied, outcomes must be a subset even when that list is empty. Older payloads lacking the field retain the prior behaviour. |
| Plan budgets | NaN budget/gain figures passed `<` comparisons | Non-finite `vs_none`, `vs_balanced`, and required `hit_gain` fail before the budget tests. |
| Next model target | NaN expected points/target passed the tolerance comparison | Non-finite expected points/target fail. |

`data-extra.json` now includes `squad_source`: entry id, picks gameweek, raw FPL chip history, and (only for a required restore) `{gw, ids}` from the pre-Free-Hit picks endpoint. This is fetched independently of `own_picks`, `fh_active` and `squad_gw`; the validator also checks the detail file's build timestamp. A failed source fetch stops the build. At the last deadline, with no next gameweek to plan, no restore is required.

Missing evidence in a required Free Hit week is an error. Older ordinary builds without the new source field get a warning to rebuild, not an assumed successful check. Existing missing-detail warnings remain warnings.

Each added/repaired check has passing and rejecting inputs in `tests/test_validate.py`, exercising `validate.main`, its exit code and saved Health errors. Source-fetch tests prove failures propagate. The timestamp warning also has good/bad input coverage.

## Other checks reviewed

- xP range, flagged-player xP, probability ranges, expected minutes, season points series, DefCon, Understat joins, minutes-model fallback, review scores/targets/streaks, journal moves/gains, player-odds probabilities and plan ids/captain/transfers/budgets have reachable failure branches. Their inputs are populated by the current builder or the explicitly named source files; none checks a field the builder never writes.
- Existing warnings for missing Understat/odds/plans/detail data, incomplete snapshots, unmatched season totals, last-six goal/assist totals, assumed targets and skipped history remain warnings. Optional sections remain conditional on their source being available.
- The validator's only broad `except` was the deadline timestamp parser. It already generated a warning on failure rather than swallowing it. The exception list is now restricted to key/type/value errors; the warning is unchanged. Missing-file handling in `load` catches only `FileNotFoundError`; malformed JSON fails loudly.

## Limits requiring broader source/model work

Two checks can detect corrupt output but cannot independently detect the builder producing the wrong underlying statistic:

1. **xP components:** `build.py` sets `appear_adj` to the exact residual needed to make components sum to total xP. The validator can now reject corrupt/empty/non-finite components, but that residual still forces a valid fresh build's sum to agree. An independent check needs separately exported calibration-intercept/rounding evidence from the projection code. Changing the residual or calibration is outside this validation-only change.
2. **Last-five starts:** `starts_record` clamps starts to the fixture count before emitting `st5`. The bounds check can reject corrupt output, but cannot reveal excess starts hidden by that clamp. An independent check needs the raw per-fixture start counts, including double-gameweek handling. No model/statistics calculation is changed here.

The source values of purchase prices are also outside the new arithmetic check: it checks FPL's selling rule against the recorded purchase and current prices, rather than re-deriving the entire transfer ledger. Planner legality beyond the existing XI-length/captain/id checks is not added by this audit.

## Validation

Fresh scratch build of entry 8122679 on **2026-11-08 at 18:42:59 UTC**: 470 players, next GW11, **0 errors and 3 warnings**. The warnings are the existing assumed targets for GW8/GW9 and missing GW11 fixture odds. Free transfers: 3; bank: £0.7m; all 15 selling prices pass. No existing warning was promoted to an error.

- Python suite: **101 passed**, including **20 new validation/source tests** with multiple good/bad subcases.
- `npm test`: **40 passed**, plus lint and whole-app checks.
- All 14 views passed at 390px and 1280px in both light and dark themes against the fresh build. The full planner/offline behaviour suite also passed. External network request failures were reported separately by the layout runner; no local site, JavaScript or overflow checks failed.
