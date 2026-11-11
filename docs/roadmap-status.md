# FPL Lab roadmap: where we left off (5 Nov 2026)

**The backlog sheet is the source of truth for what's next.** Google Sheet "FPL Lab feature backlog":
- **Board** shows what's Next, In progress and Done.
- **Cycles** shows the current two-week cycle and its 60/30/10 mix.
- **Milestones** groups the bigger work.
- **How it works** has the rules: capture first, one branch and one PR per item, and a review at the end of each cycle.

This file keeps the context and the decisions. It doesn't keep a second to-do list.

## Status at 11 Nov 2026
Written from the git log on `main`, not from the sheet. The sheet is still the source of truth; if they disagree, the sheet wins. The text below this section is as it was on 5 Nov.

Cycle 1 items:
1. **FL-063:** Done (#68).
2. **FL-061:** Done (#69).
3. **FL-054 / FL-056 / FL-057:** Done, in one PR (#70).
4. **FL-055:** Done (#72). **FL-059:** Done (#73).
5. **FL-062:** Done (#75). **FL-064:** Done (#76).
6. **FL-084:** Done (#77).
7. **FL-088 (private sync):** Done (#90). The private sync repository is set up and the old public `sync` branch has been deleted.

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
