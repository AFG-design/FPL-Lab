# FPL Analyzer (fpl-analyzer.com): review and ideas for FPL Lab (1–2 Nov 2026)

## What was checked
- **Two passes.**
  - Signed out: every public page plus the site's source code.
  - Signed in as 8122679: My Team and all eight of its tabs, Mini League (ALL OR NOTHING), Elite Meta, GW Status, Simple mode and Advanced Bonus.
- **Source read:** `v6-engine.js` (xPts), `position-fdr.js`, `fdr-changes.js`, `roadmap-engine.js` (planner), `chips-strategy.js`, `mini-league.js`, `gw-review.js`, `validation-engine.js`, `normal-mode.js` and the main `app_v119.js` (16k lines).
- **Skipped:** the LLM features (ChatFPL/Supercomputer, Gemini bonus picks). Other managers' names are left out of this note.

## Their model vs ours (don't copy)
| Area | FPL Analyzer | FPL Lab |
|---|---|---|
| Clean sheets | Lookup table from FDR (1 = 50%, 2 = 40%, 3 = 25%, 4 = 15%, 5 = 5%) × league-position multiplier | Team xGA from xG + market odds |
| DefCon | `XDEFCON` is never computed: 0.0 for every player | Modelled |
| Attack | FPL xG90/xA90 shrunk (K = 270 mins), scaled by (6 − FDR)/3; return points raised to the power 1.05 | Per-90 + team ratings + priors + calibration |
| Planner | Greedy, one move at a time, `now_cost` instead of selling price | MILP, selling prices, EO-aware variance |
| Chips | Hard-coded yields (BB 18, TC 12, FH 16, WC 22) + random noise. Signed in, BB showed +15.6 in every GW to GW38, plus an invented "projected rank gain +107,738" | From projections |
| Accuracy page | "81.6% within ±2, MAE 1.10" over about 665 players a GW, nearly all non-players | bench.py, likely starters, paired CIs |

## Bugs seen with your squad (lessons, not features)
- **War Room:**
  - It said the captain was "Raya (Confirmed Fit)". Your captain is Haaland.
  - It flagged a "Bench Boost opportunity +24" although BB is already used.
  - It showed "Demo Force On".
  - The trades started at "#2" (no #1 shown).
- **Two engines disagree.** Simple mode says Gibbs-White → Ødegaard (+2.2, one GW). The Pro planner says Gibbs-White → Mbeumo.
  - FPL Lab's "one plan every screen uses" rule is right; keep it.
- **The planner moves for tiny gains.**
  - Its own pathway table: plan 228.4 v hold 227.6 (+0.8 over 5 GWs), yet the plan makes five transfers.
  - It offered "Raya → Evanilson" (keeper for forward) as an alternative.
- **Template XI** had two keepers, including backup Dubravka (0 xP).
- **Transfer ROI** counts Wildcard and Free Hit moves as normal transfers. That inflates "sell regret" (for example "Raya sold GW3, 39 pts since").
- **Team of the Week** was still built on GW9 fixtures after GW9 had finished.
- **"Rising tonight"** is just the top 5 by transfers in.
- **Rival Spy** defaulted "you" to the league leader, so it compared him with himself (9 draws).

## Ideas worth taking (ranked)

**1. You vs the model on your own 15 (Strong).**
- The model picks the best XI and captain from your actual 15, using the projection saved before the deadline. Auto-subs, the vice-captain rule and your chip apply.
- Show both scores and both pitches, plus an unbeaten-run streak. It goes in the Review tab.
- This also fixes audit N5 (Review currently re-runs today's model). If there's no saved projection, show "no head-to-head", never a re-run.

**2. Confidence on every move (Strong).**
- Their best planner touch, worth doing properly from our simulation:
  - "Mbeumo outscores Gibbs-White over GW10–14 in 69% of simulations".
  - A "why not the runner-up?" line.
  - "If he's injured, the fallback is X".
- Map the win % to our labels: Strong, Marginal, Coin flip.
- Caveat: pairwise wins need draws from the same simulated outcomes (shared team goals) to be honest about two players from the same club. Validate the label cut-offs on past GWs.

**3. Rival "still to play" and xP swing (Strong).**
- Show players only one of you owns, ranked by projected swing, and a captain battle.
- During a live GW: the current margin and the players each side has left.
- Fix the identity to 8122679; don't default to whoever is first in the league.

**4. Your overrides on minutes and availability (Strong for use, needs care).**
- Per player: start chance, Available / Doubt / Out, and a fixture nudge. They feed Re-plan.
- Show "your override" on the card. Never save overrides into `history/`. Clear them at the deadline. Sync them like locks.

**5. Elite vs overall ownership, and who the elite bench (Marginal, cheap).**
- From the crowd sample we already take each GW:
  - The biggest "elite preference" gaps (top 10k % minus overall %) and "elite avoidance".
  - Owned vs started %, and the most-benched player.
  - Hits spent, average bench points, and chip usage %.
- Where: Rivals tab.
- Missing data: if the sample is missing for a GW, say so, not 0%.

**6. Fixture-difficulty movers (Marginal).**
- A "price changes"-style table of team attack and defence ratings that rose or fell, with the match that entered and the one that left the window.
- Split attack and defence difficulty on the fixture chips.
- Display only; do it with fix N7.

**7. Plan vs hold vs two moves, with the gap (Marginal; partly exists via `vs_roll`).**
- Always show the hold option's total next to the plan, so a +0.8 five-move plan is obvious.
- Matches your rule that strategies never move just for the sake of it.

**8. Chip ledger with real returns (Marginal).**
- For each used chip, show what it actually earned:
  - BB = bench points that GW
  - TC = the captain's extra points
  - FH = the FH XI's score minus your previous squad's score that GW
- Add a "chips renew at GW20" divider and a "use now vs best week" card from our projections.

**9. Sell regret, chips excluded (Marginal, cheap).**
- Points sold players scored after you sold them, against the player you bought. Exclude Free Hit and mark Wildcard weeks, as our ledger already does.

**10. Rotation partner finder (Marginal).**
- Pick a club. Rank other clubs whose easy fixtures alternate with it, for keeper and defender pairs over the next 5–8 GWs. Use our team ratings.

**11. Mini-league fun (Coin flip).**
- GW winner, wooden spoon, biggest climber, chips used and left per rival, points heatmap, and a last-5-GW form row.

**12. Model page transparency (Marginal).**
- Add xMins Brier and a big-misses count. Offer a download of the saved pre-deadline projections. Show the model version per GW.

**13. Deadline ownership forecast (Coin flip).**
- Project each player's ownership at the deadline from net-transfer pace.
- Only useful if Play safe needs better EO before the crowd sample exists; test that first.

**14. Test next spring (Coin flip; bench.py first).**
- A run-in motivation boost after GW30, and a rest discount from GW35 for European finalists. Backtest on 2025/26 GW31–38 first.

## Skip
- LLM chat/voice/Gemini (decided: no paid or Claude API).
- Screenshot OCR, Simple/Pro modes, translations, APK/EXE.
- Per-player floor/ceiling (we already show outcome tiles).
- Template overlap/missing/differentials (already have).
- "Transfer timing score" (average ownership when bought vs sold): the signal is too weak.

## Design notes
- **Good:**
  - "Explain this page" on every view.
  - Plain-English difficulty tooltips ("expected to concede 1.8 a game away").
  - "Showing 50 of 157" footers on long tables.
  - Honest note on the elite template ("£2.7m over budget, not a squad you could register").
  - Per-move confidence labels on the planner.
- **Bad:**
  - Many duplicate panels saying different things.
  - Animation-heavy War Room.
  - Several pages dead while their live relay was down on 1 Nov (GW Status showed a hard-coded "GW 33").
  - Our static data.json approach is more robust; keep it.
