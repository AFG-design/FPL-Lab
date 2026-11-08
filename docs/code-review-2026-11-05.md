# FPL Lab deep code review: 5 Nov 2026

Reviewed commit `1a5032e`, the whole codebase: model, build/validation/workflows, optimiser/planner and front end. This was a review only, so no code was changed. The six issues from the 4 Nov review are all still open and are not repeated here.

Labels: **R** = reproduced in an isolated test · **T** = traced in the code, not run.

## Fix first

1. **The site freezes for the whole of GW38 (R).** Once the last deadline passes there is no "next" gameweek. `build.py` then crashes on the team ratings (L1219), and `validate.py` crashes on the odds-history check (L284: `pg >= None`). Every refresh fails until the season ends, so there are no live GW38 scores and no final review. Fix: guard every next-GW section with `if next_gw`, and add a season-end test.
2. **Balanced and Play safe suggestions can create a −4 (R).** `planner.js` L26–27 and L81–82 only check hits in the week of the move. A move this week can use up the free transfer a later planned week relied on. Example: 1 FT, two moves already planned for GW11 on the rolled FT. A GW10 suggestion shows no hit pill, but adding it turns GW11 into a −4. This breaks the "Balanced and Play safe never take a hit" rule. Fix: compare total hits across all weeks.
3. **Team ratings drop during live matches (R).** `fplmodel.team_ratings` (L316) counts any fixture with a score set, and FPL sets the score at kick-off. Meanwhile `finished_only` (build.py L56) strips those teams' players, so their xG for the match reads as 0. Example: at kick-off of a 0–0 match, team 1's attack rating fell from 1.22 to 1.10 (before the market blend, which leaves about 30% of the shift). This affects every 10-minute live refresh and the second fixture of a double. Fix: skip fixtures that aren't finished, and teams still to play that GW.
4. **Refresh runs can lose history files but still deploy (T).** `refresh.yml` checks out the triggering SHA, not the latest `main`. The commit-and-push step is `continue-on-error`, so a rebase conflict on `status.json`/`prices.json`/odds silently discards that run's `history/` writes. Write-once files (absence checks, template samples, transfer-log snapshots, price nights, the last pre-deadline snapshot) are then lost for good. The git log shows no data commit between 02:16 and 09:49 today. Fix: check out `main`, retry the build on conflict, and fail loudly if the push fails near a deadline.
5. **Live auto-sub picks the wrong bench player (R).** `live.js` L55 skips bench players whose match hasn't started. If bench 1 is yet to play, it brings on bench 2 and shows "Auto-sub: counts", but FPL would wait for bench 1. Home's live points, the live rank and "Your live points" are then wrong. Fix: take the first eligible bench player in order, and mark him "if he plays".

## Medium

**Model**
- **A mid-season transfer carries the player's old xG to his new club (T).** `team_gw_xg`/`opp_of` use today's club for every past GW (fplmodel L265–270, L564). Example: a January move inflates the buying club's attack for GW1–20.
- **Chances created read 0 for players without a shot (R).** In understat.py L185/L218, 34 of 453 players have key passes but 0 chances created. Fix: key the lookup by Understat team + id.
- **A flagged player with no chance gets 50% even when his return date rules him out (R).** fplmodel L778–782. Example: "Suspended until 21 Nov" gives 50% next GW. Fix: check the return date before the 50% default.
- **Backtests use hindsight (T).** The backtest uses today's `status == "u"`, penalty order and club for past weeks, which flatters the backtest scores. Worth fixing before trusting the next model comparison.

**Build and validation**
- **The set-piece change history is wiped by one failed fetch (R).** It is stored only in the deployed data.json (build.py L1184–1201). Fix: keep it in `history/setpieces.json`.
- **One failed picks fetch empties Review, You vs the model and the journal, with no message (T).** build.py L890–893: a broad `except` sets `past = {}`. Fix: fetch per GW, list failures, and add validate.py warnings.
- **The absence-rule check can save its "before" snapshot after the deadline (R).** `absence_gw8.json` was built at 19:43, after the 17:30 deadline (build.py L558–567). Fix: drop `+ [cur_gw]`, and only write before the deadline.
- **Missing model inputs drop out silently (T).** If priors, odds, Understat set pieces, the status log or europe.json fail to load, the model runs on without saying so (build.py L74–106, L148). Fix: record each input's status in `meta.sources`, and warn or error in validate.py.

**Planner**
- **A roll plan is exempt from the "no moves for the sake of it" rule (R).** optimise.py L263 `key != "roll"`. Chase can end up recommending a transfer worth −0.8 vs doing nothing. Fix: replace a failing roll plan with the keep-squad plan.
- **Holding four players from one club makes every plan infeasible (R).** The club limit is a hard ≤3, even for the keep-squad baseline (optimise.py L107, plan-solver.js L84). A January move between PL clubs could cause this. Fix: cap each club at max(3, current count) and never let it increase. The FPL rule needs confirming.
- **Browser Re-plan uses a smaller shortlist than the server (R).** plan-solver.js uses 10/26/30/16 vs optimise.py's 14/40/45/25. On synthetic squads it came out 1.2–5.1 pts worse over 5 GWs, and Play safe/Chase budgets are measured against that weaker plan. Fix: share the pool sizes (check HiGHS timing first).
- **Switching strategy on a hand-edited plan leaves a stale "vs no transfers" baseline (R).** events.js L25–29 / plan.js L144. Fix: clear `_base` on a mode change.

**Front end**
- **A flagged player with no chance shows as "0%" (R).** player-sheet.js L54/59, players.js, watchlist.js and team-sheet.js all use `chance ?? 0`, which states a figure FPL never gave. Fix: show "!" / "no chance given", as `flag()` already does.
- **Rivals live points use a different basis from Home (T).** Rivals uses no provisional bonus and takes hits off during live play, but outside live play FPL's `event_total` (before hits) is used. Your own row can sit 3+ pts below Home during matches. Review's live table has the same gap.

## Low
- GK save points are understated when the chance of playing is below 100% (R; at 50%, 0.20 vs 0.33).
- Defensive contribution: hits are counted per GW but applied per fixture, which overstates doubles. It is also gated on 60+ minutes, though FPL has no such rule (T).
- A news item with a 29 Feb return date posted in a non-leap year would crash `project()` (R).
- Silent defaults for new signings with no minutes (0.75 / 75 / 20 mins, not marked assumed). Also `make_priors` never writes `start_rate`, and crowd.py defaults a missing rank to 100k with `complete` always True (T).
- "Last 5 starts" and 4-GW totals count the current GW for clubs that haven't played yet (R).
- Some validate.py checks can't fail (the Free Hit restore check), and there are no range checks on free transfers, bank or sell price (T).
- priors.yml and odds-archive.yml push without pulling, and the `afg.py records` failure is hidden (T).
- The Chips page crashes ("couldn't be drawn") when the build has no plans (R).
- Match cards don't double the vice when he takes the armband (T).
- The captaincy text says "near your rank" when it has fallen back to the top-10k sample (T).
- Undo after a deadline rollover restores a past-week move as a free transfer (R).

## Worth knowing
- **Your synced plan is public.** The `sync` branch of the public repo holds `plan.json`: your plan, watchlist and journal notes. The sync dialog says only the token stays on the device. Either accept this and say so in the dialog, or move the sync to a private repo or gist.
- **Test coverage.** There are no unit tests for fplmodel, xmins, odds, odds_players, understat, crowd or make_priors.
- **What held up.** The server and browser solvers agree exactly given the same shortlist. Selling prices, formation, budget and the 5-FT cap are correct. News and names are escaped everywhere, so there's no XSS found. The service worker caches correctly. All 13 screens load at 390px and 1280px in dark and light mode with no JS errors.

## Validation
- Python unit tests: 60/60 passed. `npm test` (lint + site checks): passed.
- A fresh build of data.json in a scratch copy (GW10) passed `validate.py` with 0 errors and 3 expected warnings.
- The browser sweep ran against that build.
- Not run: backtest.py, bench.py, and the planner findings on your real squad (all planner repros used synthetic data).

## Order of work
Do the GW38 crash and the planner hit rule first. Then the live-match rating bug and the Refresh push losses, since they quietly corrupt data and history. Then auto-subs, alongside the earlier "complete plan" trio (Use plan / Undo / saved-path comparison).
