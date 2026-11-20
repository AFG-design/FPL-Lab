# FPL Lab roadmap: where we left off (20 Nov 2026)

**The backlog sheet is the source of truth for what's next.** Google Sheet "FPL Lab feature backlog":
- **Board** shows what's Next, In progress and Done.
- **Cycles** shows the current two-week cycle and its 60/30/10 mix.
- **Milestones** groups the bigger work.
- **How it works** has the rules: capture first, one branch and one PR per item, and a review at the end of each cycle.

This file keeps the context and the decisions. It doesn't keep a second to-do list.

## Status at 20 Nov 2026
Checked against the git log on `main` and the backlog sheet on 20 Nov (evening). The sheet is still the source of truth.

- **Cycle 1 reviewed 19 Nov: 34 of 34 shipped.** FL-172 (this file) carried over to Cycle 2.
- **Cycle 2 (20 Nov–3 Dec), main goal v1.4 Model check-ups.** Merged 19–20 Nov:
  - Model, on probation (re-check list at the top of `docs/model-log.md`): FL-176 DefCon priors use DefCon minutes only (#237), FL-212 bench priors use FPL's backfilled 2024/25 DefCon (#240), FL-177 DefCon `dc_r 10` tail (#241), FL-224 DefCon shrinkage `dc_blend 15` (#247, hot-run check #248), FL-165 falling free-transfer scale switched on (#244, #245).
  - Tested, not adopted: FL-214 per-player European cut (#242), FL-160 defender bonus multiplier `def_bonus_mult`, kept at 1.0 (#246), FL-216 Bzzoiro set-piece xG as an Understat stand-in (#243).
  - Data: FL-213 2025/26 Europa and Conference League dates (#236).
  - Features and fixes: FL-223 mini-league title odds (#238), FL-207 98 px phone header (#230), FL-193, FL-196, FL-187, FL-192, FL-195, FL-202, FL-208, FL-211; reports FL-198 (accessibility, #235) and FL-210 (`--hi` uses, #234); FL-206 visual audit 2 (#207).
- **Also merged on the evening of 18 Nov,** after the 18 Nov section below was written: #208–#223 (FL-179 to FL-186, FL-197, FL-203, FL-204, FL-205, FL-209, and the wide-monitor layout #208–#209).
- **ID clash fixed (20 Nov):** #247 and #248 used FL-224, which was already the Gemini team-news labels test. Git can't be renamed, so FL-224 now means `dc_blend` in the sheet and the Gemini test is **FL-233**.
- **Still open in Cycle 2:** FL-098 backup scheduler (first real test: GW11 window, Sat 21 Nov 05:00–11:00 UTC), FL-175 and FL-174 (start chance), FL-199 team-news collector, FL-226 light-mode focus rings, FL-134 ep_next blend (after GW12), FL-021 player-odds re-test (GW12–13), FL-229 style data (PR #249 open).
- **Dropped 20 Nov:** FL-215 ClubElo test. ClubElo's API returned HTTP 502 on every try in both Antigravity batches.
- **Understat still down since 1 Nov.** The site keeps the last good data and warns; FL-229's backfill waits until Understat is back.
- **FL-230 full-season replay & lever priorities (20 Nov, analysis PR):** Replaying GW1–38 with chips on `2024-25` and `2025-26` (5 seeds, live `FT_SCALE`, 0 rule violations; likely flattering because these seasons tuned current settings) puts FPL Lab at roughly **~620k–1.4M** overall (**~170–290 pts** short of Top 10k; ~30–50 pts of 2024-25's gap is the omitted Assistant Manager chip, and replays run without live injury flags). Even a weekly **hindsight** strategy oracle only adds **+24–25 pts** over the best fixed strategy. **Build order to close the gap:**
  1. **Start-chance & live team news first** (FL-174, FL-175, FL-199, FL-131) — missed starts and captain blanks cost far more than planner tuning.
  2. **Underlying projection & DGW/captaincy accuracy** (FL-053 DGW under-projection, FL-134 `ep_next` blend, FL-021 player odds, FL-229 style data) — closing ~170–290 pts needs ~4.5–7.5 real pts/GW from better projections.
  3. **Chip-aware multi-GW transfer setup** (FL-005 chip pins by GW) — reactive chip thresholds (Lever 3a, −3 pts pooled) didn't beat a simple DGW/BGW rule; real chip gain requires planning transfers *into* pinned chip weeks.
  4. **Skip / do not build:** automated strategy switching (Lever 3b, −37 pts vs best fixed; hindsight ceiling only +24 pts) and selective hits for Balanced (Lever 3c, −25 to −44 pts; keep `MAX_HITS["balanced"] = 0`).

## Status at 18 Nov 2026
Checked against the git log on `main` and the backlog sheet on 18 Nov. The sheet is still the source of truth; the sections below this one are kept as they were written.

- **Cycle 1 (6–19 Nov): all 34 items done.** That includes four rows added on 18 Nov for work that shipped without an FL ID: FL-168 squad rating floor (#151), FL-169 this-week transfer comparisons (save, keep, captain, Bench Boost; direct commits 14–15 Nov), FL-170 saved plans explain what changed since their last review (direct commit 15 Nov), and FL-040 mini-league extras, delivered by the Rivals redesign (#174) and the pinned rival on Current GW.
- **Cycle 2 (20 Nov–3 Dec): 8 of 9 done before it starts.** FL-090 Planner redesign (#165, follow-ups #167, #170, #171), FL-149 (You vs the model keeps its own tab), FL-156 Players review (#157–#161), FL-159, FL-161, FL-130 (#185), FL-163 (#186), FL-162 (#187; live model unchanged). Left: **FL-021**, the player-odds re-test at GW12–13, now set to Next.
- **Cycles 3 and 4 need re-planning at the 19 Nov review.** Everything proposed for them (FL-030, FL-065, FL-053, FL-005) was done on 13 Nov, so the "Proposed later cycles" section below is out of date.
- **Open backlog:** FL-160 clean sheets and defender scoring as one package, FL-131 xmins_sell decision (shadow check after GW14, decide before the GW15 deadline), FL-134 ep_next blend, FL-135 decision replay on 2026/27, FL-158 build.py except blocks, FL-164 captain card wording, FL-165 banked free transfer value, FL-171 mini-league points heatmap (split from FL-040).
- **In progress:** FL-098 backup scheduler. The first real test is the GW11 deadline window, Sat 21 Nov 05:00–11:00 UTC.
- **Process note:** several changes on 14–15 Nov went straight to `main` without an FL ID or a PR. Keep to one ID, one branch and one PR per item so the cycle review can count them.

## Status at 11 Nov 2026
Written from the git log on `main`, not from the sheet. The sheet is still the source of truth; if they disagree, the sheet wins. The text below this section is as it was on 5 Nov.

Cycle 1 items:
1. **FL-063:** Done (#68).
2. **FL-061:** Done (#69).
3. **FL-054 / FL-056 / FL-057:** Done, in one PR (#70).
4. **FL-055:** Done (#72). **FL-059:** Done (#73).
5. **FL-062:** Done (#75). **FL-064:** Done (#76).
6. **FL-084:** Done (#77).
7. **FL-088 (private sync):** Done (#90). Still to do by hand: set up the private sync repository on each device, then delete the old public `sync` branch.

Also merged since 5 Nov, outside the Cycle 1 list: FL-096 (#71, #82), FL-091 (#74), FL-077 (#78), FL-087 (#79), FL-086 (#80), FL-085 (#81), FL-081 (#83), FL-071 (#84), FL-076 (#85); and from the 10 Nov audit, #86–#91 (refresh-gap warning, Understat staleness, odds carry-over, source checks, private sync, Rivals tile).

**IDs (from 5 Nov):** every item is FL-nnn, numbered in the order it was added and never reused. Branches and PRs use the same ID (`fix/fl-063-refresh-push`, PR title "FL-063: …"). Old IDs (C1, B10, M2 …) are in the sheet's Old ID column; the model log and older docs still use them.

## Scheduled checks
- **History check:** Sundays 08:37. Checks that last GW's write-once history files were saved before the deadline. Messages only when something is missing. Logs to history-check-log.md (kept outside the repo).
- **Cycle review:** Thursdays 17:39, acting only on the last day of a cycle (first one 19 Nov). Marks merged items Done, fills in the Cycles row, and proposes the next cycle for approval.
- **Weekly hallucination audit:** Tuesdays. The 3 Nov run failed because the usage limit had been reached.

## Done 5 Nov
- **#66 (FL-058, was B5):** the journal saves the start chance the forecast actually used.
- **#67:** CLAUDE.md in the repo is the single source of build rules.
- **Deep code review:** docs/code-review-2026-11-05.md. Its findings are FL-060 to FL-089 (were B7–B36).
- **Backlog sheet restructured:** types, status flow, Critical priority, milestones v1.1–v1.6 plus Housekeeping, the Board / Cycles / Milestones / How it works tabs, saved filter views, and FL-nnn IDs. The old layout is kept as the "Archive (before 5 Nov)" tab.
- **Decided: FL-088 (B35), synced plan privacy.** Move sync to a private repo (a secret gist is only unlisted, so not chosen), then delete the old public `sync` branch so its history goes too, and reword the sync dialog. Added to Cycle 1.

## Done 4 Nov
- **FL-035 (was F1), You vs the model (#56–#61):** your actual points after hits against the model's target. The record so far is 2–0–0, and the GW10 target is 50.
- **FL-051 (was D5), Decision journal (#62–#65, with FL-052 / D6 merged in):** an automatic entry each GW from GW10, Why / Why not? tags, 5-GW results and a season summary.
- **Fix:** the model's suggested moves are now paired like for like by position.

## Dropped (4 Nov)
FL-036 (F2), and with it FL-047 and FL-048 (D1, D2); FL-033 (M4); FL-049 (D3). FL-040 (F12) is on hold.

## Cycle 1: 6–19 Nov
Main goal: v1.1 Plan you can trust. All of it is Claude Code work, one PR per branch.
1. **FL-063 (B10), Critical:** refresh pushes can lose write-once history files. Do this first.
2. **FL-061 (B8):** Balanced and Play safe can create a hidden −4 in a later week.
3. **FL-054 / FL-056 / FL-057 (B1/B3/B4), on one branch:** Use plan, Undo and saved paths all work from the complete plan.
4. **FL-055 (B2), FL-059 (B6):** the Re-plan captain baseline, and the Triple Captain display.
5. **FL-062 (B9), FL-064 (B11):** live-match team ratings, and the live auto-sub order.
6. **FL-084 (B31), tech debt:** validate.py checks that can actually fail.
7. **FL-088 (B35), Housekeeping:** move the synced plan to a private repo (`fix/fl-088-private-sync`). Added 5 Nov; it takes the main-goal share from 55% to 50%.

FL-060 (B7, the GW38 crash) was moved out of Cycle 1 on purpose. It's cheap but doesn't bite until May, so it sits in v1.2 Data you can trust.

## Proposed later cycles (confirm at each cycle review)
- **Cycle 2 (20 Nov–3 Dec): v1.4 Model check-ups.**
  - FL-031 (M2) together with FL-068 (B15): the injury rules check and the hindsight leaks, in the same backtest run.
  - FL-021 (K4): re-test the player odds once at GW12–13, then close it either way.
- **Cycle 3 (4–17 Dec): v1.5 January window.**
  - FL-030 (M1), new-signing minutes.
  - FL-065 (B12), so a mid-season move doesn't carry a player's old xG to his new club.
- **Cycle 4 (18–31 Dec): v1.6 Doubles & 2nd-half chips.**
  - FL-053 (M6), the double-gameweek under-projection.
  - Then FL-005 (C8), chip pins by GW, about 5–6 h across three PRs. It must be ready before the second-half chips (from GW20) enter the 5-GW window.

## First things to check next
- The GW10 journal entry saved at the deadline (Fri 6 Nov 18:30), and its first results after GW10.
- The GW10 head-to-head: your points after hits against the target of 50.
- The Cycle 1 review on 19 Nov (the scheduled task drafts it).
