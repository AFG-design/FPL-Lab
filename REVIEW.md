# Reviewing an FPL LAB PR

What to look for in this codebase, drawn from CLAUDE.md, AGENTS.md and past audits in `docs/`. CLAUDE.md is the rule
book; this is the checklist. If they disagree, CLAUDE.md wins.

Tag every finding:
- **Important**: breaks a rule below, or would show the owner a wrong number or wrong advice. Must be fixed before merge.
- **Nit**: wording, naming, a missing comment. Fix if cheap.
- **Pre-existing**: a problem the PR didn't cause. Note it (file and line) for a follow-up; don't block the PR on it.

## 1. Hindsight leaks and double counts (model, backtest, review)
- A backtest or "projected before the deadline" figure may only use what was known at that deadline. Past leaks:
  - today's `status == "u"` zeroing a player in every past week (fixed 1 Nov, PR #39);
  - today's club for past GWs, so a January move inflates the buying club's attack (code review 5 Nov);
  - injury flags rebuilt from today's notes; `use_out` skipping hindsight injury weeks (model log, FL-068);
  - Review's "projected before the deadline" re-run with today's model and data (hallucination audit 2).
  Ask: does every input to a past-week number come from a snapshot (`history/`, status log) dated before that deadline?
- Double counts: the same effect entering twice. Examples:
  - FPL `expected_goals` already includes penalties, so a penalty-taker boost on top counts them twice (audit 2);
  - a flagged player's minutes cut by both a low start chance and the ×0.75 flag (audit 2, N1);
  - a fixture counted twice in a data file (model log, GW10 double-counted match).
- A model change (`fplmodel.py`, params, priors, odds) needs the backtest and bench evidence and a decision-table row
  in the PR (CLAUDE.md, Model changes). No evidence, or no row named: **Important**.
- `history/` files are write-once. Anything that could lose or overwrite them is **Important** (AGENTS.md P0). A PR
  should never commit `history/` changes from a local build.

## 2. Units
| Quantity | Unit in data.json | Watch for |
|---|---|---|
| Prices, bank, team value | £m, one decimal (`now_cost / 10`) | tenths mixed with £m; float sums not rounded to 0.1 |
| Selling price | £m: purchase + half the rise, rounded down to £0.1m; a fall taken in full (`fplSell`) | today's price used as selling price |
| `chance` | FPL's 0–100, or `null` (no chance given) | `chance ?? 0` turning "not given" into "0%" (code review 5 Nov) |
| `p_start`, `psub`, `dc_rate`, `dist` | probabilities 0–1 | shown as "% of recent games" when it is a weighted chance (audit 2, N3) |
| `nailed` | 0–100 | divided twice, or compared to a 0–1 probability |
| `xmin` | expected minutes 0–90 per match | summed over a double gameweek without saying so |
| `eo` | fraction, captain counts 2 | percentages; captain counted once |
| Price projection | % of the way to a change; ≥100 means "tonight" (`priceTonight`) | another cut-off for "tonight" |
| xP | points for one GW, or a stated span (`xp1`, `xp5`) | a 5-GW figure labelled as next GW |

## 3. On-page wording must test what the data tests
- A sentence that asserts a fact ("out", "injured", "tonight", "starts", "didn't play") must check the same field the
  data uses (`status`, `news`, `chance`, the price threshold), not a proxy. Past example: "missed his club's last game
  with no injury news" fired on 0 minutes alone, next to an injury flag (audit 2, N2). **Important**.
- Every number says what it is: xP next GW or over N GWs, start chance or real starts, projected or actual. An
  unlabelled number is a **Nit**; one labelled wrongly is **Important**.
- Missing, late or ambiguous input is either shown (`assumed`, "Unavailable", a Health warning) or fails loudly. A
  silent default is **Important** (CLAUDE.md, Missing data). The PR must say what happens when the input is missing.

## 4. Planner and server parity, and FPL's rules
- `optimise.py` (server plans) and `site/plan-solver.js` (Re-plan) must solve the same problem with the same settings
  (`plan_rules`, FL-075). A constraint added to one and not the other is **Important**. So is a planner setting copied
  into the browser instead of read from `plan_rules`. `tests/test_planner_parity.py` checks the plan value only, so
  read both diffs.
- `site/js/core/plan.js` (`ftTable`, `bankAt`, `squadAt`, `scoreMoves`) scores plans in the Planner. It must agree with
  both solvers on hits, free transfers (1 a week, up to 5), chips and selling prices.
- FPL rules a plan must never break: budget (bank ≥ £0), 15 in 2/5/5/3, 3 a club (FL-074 exception), a valid XI,
  hits only for moves beyond free transfers, one chip a GW. `tests/test_plan_properties.py` and
  `tests/plan-properties.mjs` check these on random inputs; a change to the rules should keep them passing unedited.
- Balanced and Play safe never take a hit. Only Chase rank may take a −4, within `CHASE_BUDGET`. Every strategy weighs
  rolling the transfer. Breaking any of these is **Important** (CLAUDE.md, Tabs and planner).

## 5. Phone layout and both themes
- Check the screens at ~390px and ~1280px in dark and light mode (CLAUDE.md, Testing). `npm run layout` catches JS
  errors, error cards and sideways scroll. It doesn't catch text that's cut off, overlaps or is too small, so look at
  the screenshots CI keeps.
- New tables scroll inside `.tablebox`, never the page. New colours need contrast in both themes
  (`scripts/contrast_check.py`). Tap targets on touch (`scripts/tap_check.py`).
- Keep the existing design: AFG suggestion, Model and Data health stay where they are.

## 6. Checks and the PR itself
- A new data field or join comes with a `validate.py` check where it's cheap. A check that can't fail is **Important**
  (AGENTS.md P1).
- A PR must not edit the test or check that judges it (tests, `validate.py`, `check.yml`) without explaining why that
  check was wrong. No skipped, retried, slept or loosened tests (CLAUDE.md, Verification).
- The PR says what was wrong, what changed, what it's worth, and includes the verify skill's PASS/FAIL summary.
- No paid data, no Claude API in the app, and no FPL Review data in the repo or on the site.
