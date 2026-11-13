# Remote branches on 13 Nov 2026 (153 besides main)

- **Keep** 5: open PRs.
- **Decide** 9: no merged PR, so their work may not be in main. Delete only the ones you don't want.
- **Safe to delete** 139: the PR was merged, or closed for a recorded reason with the work landed elsewhere.

Main's history was rewritten at some point, so many merged branches no longer share commits with main; whether a
branch's PR was merged is the reliable test, not commit ancestry. Checked: every merged-PR branch that is only 1-2
commits off main has its tip exactly at the head its PR merged, so deleting it loses nothing.

## Keep

| Branch | Last commit | Why |
|---|---|---|
| `fix/fl-053-double-gameweeks` | 2026-11-13 | open PR #142 |
| `fix/fl-109-record-from-gw10` | 2026-11-13 | open PR #144 |
| `fix/fl-143-chip-ledger` | 2026-11-13 | open PR #145 |
| `fix/fl-147-fpl-school` | 2026-11-13 | open PR #146 |
| `fix/fl-153-rival-autosubs` | 2026-11-13 | open PR #143 |

## Decide

| Branch | Last commit | Why |
|---|---|---|
| `feat/fplr-import` | 2026-10-31 | PR #32 closed unmerged: kept for FL-095 (private FPL Review import, on hold) |
| `feat/strategy-switch-test` | 2026-11-01 | no PR was ever opened: work that may not be in main |
| `feat/transfer-reason` | 2026-11-04 | no PR was ever opened: work that may not be in main |
| `model-absence-adj` | 2026-10-29 | no PR was ever opened: work that may not be in main |
| `model-bonus-fixture` | 2026-10-29 | no PR was ever opened: work that may not be in main |
| `model-fixture-cs` | 2026-10-28 | no PR was ever opened: work that may not be in main |
| `model-player-prior` | 2026-10-28 | no PR was ever opened: work that may not be in main |
| `stress-test` | 2026-10-23 | PR #9 closed unmerged: holds the 23 Oct stress-test report; FL-140, its last open item, is done (#140) |
| `xmins-selling` | 2026-10-31 | no PR was ever opened: work that may not be in main |

## Safe to delete

| Branch | Last commit | Why |
|---|---|---|
| `accuracy-compare` | 2026-10-24 | PR #15 merged |
| `afg-suggestion` | 2026-10-23 | PR #8 merged |
| `chore/audit-safeguards` | 2026-10-29 | PR #21 merged |
| `chore/fl-084-validate-checks` | 2026-11-08 | PR #77 merged |
| `chore/fl-096-shared-docs` | 2026-11-08 | PR #71 merged |
| `claude-md-single-source` | 2026-11-05 | PR #67 merged |
| `claude/practical-hypatia-qn8n8g-a1-refresh-gap` | 2026-11-11 | PR #86 merged |
| `claude/practical-hypatia-qn8n8g-a2-understat-stale` | 2026-11-11 | PR #87 merged |
| `claude/practical-hypatia-qn8n8g-b1-odds-partial` | 2026-11-11 | PR #88 merged |
| `claude/practical-hypatia-qn8n8g-b10-docs` | 2026-11-11 | PR #97 merged |
| `claude/practical-hypatia-qn8n8g-b14-source-checks` | 2026-11-11 | PR #89 merged |
| `claude/practical-hypatia-qn8n8g-b7-one-cs-formula` | 2026-11-11 | PR #94 merged |
| `claude/practical-hypatia-qn8n8g-b9-chances-created` | 2026-11-11 | PR #95 merged |
| `claude/practical-hypatia-qn8n8g-c2-price-wording` | 2026-11-11 | PR #96 merged |
| `claude/practical-hypatia-qn8n8g-c5-private-sync` | 2026-11-11 | PR #90 merged |
| `claude/practical-hypatia-qn8n8g-roadmap-fl088` | 2026-11-11 | PR #98 closed unmerged: the roadmap doc was replaced by the backlog sheet |
| `claude/practical-hypatia-qn8n8g-u2-rivals-avg-pts` | 2026-11-11 | PR #91 merged |
| `claude/practical-hypatia-qn8n8g-u4-columns-picker` | 2026-11-11 | PR #92 merged |
| `claude/practical-hypatia-qn8n8g-u6-vsmodel-contrast` | 2026-11-11 | PR #93 merged |
| `feat/centred-cards` | 2026-11-04 | PR #52 merged |
| `feat/d5a-journal` | 2026-11-04 | PR #62 merged |
| `feat/d5b-reasons` | 2026-11-04 | PR #63 merged |
| `feat/d5c-outcomes` | 2026-11-04 | PR #64 merged |
| `feat/d5d-summary` | 2026-11-04 | PR #65 merged |
| `feat/deadline-snapshots` | 2026-11-04 | PR #50 merged |
| `feat/f1a-scoring` | 2026-11-04 | PR #56 merged |
| `feat/f1b-pick` | 2026-11-04 | PR #57 merged |
| `feat/f1c-head-to-head` | 2026-11-04 | PR #58 merged |
| `feat/f1d-vs-model-tab` | 2026-11-04 | PR #59 merged |
| `feat/f1e-streak-card` | 2026-11-04 | PR #60 merged |
| `feat/f1f-no-saved-forecast` | 2026-11-04 | PR #61 merged |
| `feat/home-two-views` | 2026-11-03 | PR #43 merged |
| `feat/lineup-styles` | 2026-11-03 | PR #45 merged |
| `feat/longer-fixture-horizon` | 2026-11-04 | PR #55 merged |
| `feat/move-reason` | 2026-11-04 | PR #53 merged |
| `feat/one-confidence-scale` | 2026-11-04 | PR #51 merged |
| `feat/plan-expiry` | 2026-11-04 | PR #54 merged |
| `feat/planner-strategy-tabs` | 2026-10-31 | PR #33 merged |
| `feat/running-scorelines` | 2026-11-03 | PR #46 merged |
| `feat/setpiece-tags` | 2026-11-04 | PR #48 merged |
| `feat/squad-uplift` | 2026-11-04 | PR #49 merged |
| `feat/strategy-risk-budgets` | 2026-11-01 | PR #35 merged |
| `feat/transfer-paths` | 2026-11-03 | PR #44 merged |
| `fix-live-hits` | 2026-10-23 | PR #12 merged |
| `fix-numpy` | 2026-10-22 | PR #4 merged |
| `fix/audit-2` | 2026-10-29 | PR #20 merged |
| `fix/benchmark-hindsight` | 2026-11-01 | PR #39 merged |
| `fix/data-validity` | 2026-10-29 | PR #19 merged |
| `fix/detail-stats-retry` | 2026-11-03 | PR #42 merged |
| `fix/dgw-sim-seeds` | 2026-11-01 | PR #40 merged |
| `fix/escape-news` | 2026-11-04 | PR #47 merged |
| `fix/fl-030-new-signings` | 2026-11-13 | PR #138 merged |
| `fix/fl-031-injury-rules` | 2026-11-13 | PR #133 merged |
| `fix/fl-054-complete-plan` | 2026-11-07 | PR #70 merged |
| `fix/fl-055-replan-captain` | 2026-11-08 | PR #72 merged |
| `fix/fl-059-tc-display` | 2026-11-08 | PR #73 merged |
| `fix/fl-060-season-end` | 2026-11-12 | PR #99 merged |
| `fix/fl-061-hits-all-weeks` | 2026-11-07 | PR #69 merged |
| `fix/fl-062-live-ratings` | 2026-11-08 | PR #75 merged |
| `fix/fl-063-refresh-push` | 2026-11-07 | PR #68 merged |
| `fix/fl-064-live-autosub` | 2026-11-08 | PR #76 merged |
| `fix/fl-065-xg-club-then` | 2026-11-13 | PR #137 merged |
| `fix/fl-067-return-date` | 2026-11-13 | PR #134 merged |
| `fix/fl-068-honest-backtests` | 2026-11-13 | PR #132 merged |
| `fix/fl-069-setpiece-history` | 2026-11-12 | PR #100 merged |
| `fix/fl-070-picks-per-gw` | 2026-11-12 | PR #101 merged |
| `fix/fl-071-absence-snapshot` | 2026-11-10 | PR #84 merged |
| `fix/fl-072-missing-inputs` | 2026-11-12 | PR #103 merged |
| `fix/fl-073-roll-profit-rule` | 2026-11-12 | PR #127 merged |
| `fix/fl-074-four-from-one-club` | 2026-11-12 | PR #128 merged |
| `fix/fl-075-shared-planner-settings` | 2026-11-12 | PR #129 merged |
| `fix/fl-076-strategy-baseline` | 2026-11-10 | PR #85 merged |
| `fix/fl-077-no-chance-flag` | 2026-11-08 | PR #78 merged |
| `fix/fl-078-live-points-basis` | 2026-11-12 | PR #104 merged |
| `fix/fl-079-gk-saves` | 2026-11-13 | PR #135 merged |
| `fix/fl-080-defcon-per-fixture` | 2026-11-13 | PR #139 merged |
| `fix/fl-081-return-date` | 2026-11-09 | PR #83 merged |
| `fix/fl-082-assumed-defaults` | 2026-11-13 | PR #136 merged |
| `fix/fl-083-form-windows` | 2026-11-12 | PR #105 merged |
| `fix/fl-085-chips-no-plans` | 2026-11-09 | PR #81 merged |
| `fix/fl-086-vice-match-cards` | 2026-11-09 | PR #80 merged |
| `fix/fl-087-captaincy-sample` | 2026-11-09 | PR #79 merged |
| `fix/fl-091-odds-collector` | 2026-11-08 | PR #74 merged |
| `fix/fl-092-upcoming-odds` | 2026-11-12 | PR #121 merged |
| `fix/fl-093-returning-players` | 2026-11-12 | PR #122 merged |
| `fix/fl-096-workflow-push` | 2026-11-09 | PR #82 merged |
| `fix/fl-108-one-recommended-plan` | 2026-11-12 | PR #125 merged |
| `fix/fl-109-actual-vs-actual` | 2026-11-12 | PR #126 merged |
| `fix/fl-110-profit-vs-roll` | 2026-11-12 | PR #130 merged |
| `fix/fl-111-hourly-refresh` | 2026-11-12 | PR #119 merged |
| `fix/fl-112-odds-one-row` | 2026-11-12 | PR #120 merged |
| `fix/fl-113-recent-priors` | 2026-11-12 | PR #123 merged |
| `fix/fl-116-dead-code` | 2026-11-12 | PR #124 merged |
| `fix/fl-117-workflows` | 2026-11-12 | PR #108 merged |
| `fix/fl-118-skip-duplicate-solves` | 2026-11-12 | PR #118 merged |
| `fix/fl-120-protect-news-prices` | 2026-11-12 | PR #102 merged |
| `fix/fl-122-tab-strip-scroll` | 2026-11-12 | PR #116 merged |
| `fix/fl-123-text-contrast` | 2026-11-12 | PR #110 merged |
| `fix/fl-124-tap-targets-aria` | 2026-11-12 | PR #111 merged |
| `fix/fl-125-planner-gain` | 2026-11-12 | PR #109 merged |
| `fix/fl-126-afg-lean-wording` | 2026-11-12 | PR #115 merged |
| `fix/fl-131-xmins-sell-shadow` | 2026-11-13 | PR #131 merged |
| `fix/fl-137-bench-all-players` | 2026-11-12 | PR #117 merged |
| `fix/fl-138-audit-2-check` | 2026-11-12 | PR #112 merged |
| `fix/fl-140-optimiser-silent` | 2026-11-13 | PR #140 merged |
| `fix/fl-148-chase-limit-docs` | 2026-11-12 | PR #107 merged |
| `fix/fl-152-crowd-history` | 2026-11-12 | PR #106 merged |
| `fix/fl-154-accuracy-claims` | 2026-11-12 | PR #113 merged |
| `fix/fl-155-shotmap-freshness` | 2026-11-12 | PR #114 merged |
| `fix/free-hit-squad` | 2026-11-01 | PR #38 merged |
| `fix/journal-start-chance` | 2026-11-05 | PR #66 merged |
| `fix/model-log-dates` | 2026-11-13 | PR #141 merged |
| `fix/replan-keeps-lineups` | 2026-11-01 | PR #41 merged |
| `fix/replan-vice-offline` | 2026-11-01 | PR #37 merged |
| `fixes-batch1` | 2026-10-23 | PR #10 merged |
| `fixes-batch2` | 2026-10-23 | PR #11 merged |
| `layout-check-ci` | 2026-10-30 | PR #25 merged |
| `leaders-matchday` | 2026-11-01 | PR #36 merged |
| `model-bench` | 2026-10-22 | PR #2 merged |
| `model-display-parts` | 2026-10-31 | PR #28 closed unmerged: rejected on a fresh backtest, 12 Nov |
| `model-eval-horizons` | 2026-10-28 | PR #17 merged |
| `model-sim` | 2026-10-22 | PR #3 merged |
| `model-xmins-selling` | 2026-10-31 | PR #29 closed unmerged: re-landed as #131, merged 13 Nov |
| `odds-archive-backfill` | 2026-10-30 | PR #24 merged |
| `odds-errors` | 2026-10-23 | PR #6 merged |
| `odds-names` | 2026-10-23 | PR #7 merged |
| `odds-players-fixes` | 2026-10-31 | PR #30 merged |
| `player-odds` | 2026-10-23 | PR #5 merged |
| `quick-fixes-nav-solver` | 2026-10-24 | PR #16 merged |
| `stats-ga-defcon-race` | 2026-10-31 | PR #34 merged |
| `test-bench-parts` | 2026-10-31 | PR #26 merged |
| `transfer-log` | 2026-10-29 | PR #18 merged |
| `ui-redesign` | 2026-10-22 | PR #1 merged |
| `ui-round1-type` | 2026-10-24 | PR #13 merged |
| `ui-round2-texture` | 2026-10-24 | PR #14 merged |
| `weekly-retune` | 2026-10-29 | PR #22 closed unmerged: auto-retune bypasses the model-change rule (closed 12 Nov) |
| `xmins-minutes-model` | 2026-10-30 | PR #23 merged |
| `xmins-selling-odds` | 2026-10-31 | PR #27 closed unmerged: odds half landed as #30; the xMins half was superseded by #29 and then #131 |
| `xp-table` | 2026-10-31 | PR #31 merged |

## Delete the safe ones

Run on your own machine: branch deletion is blocked from Claude sessions (git proxy 403).

```bash
git push origin --delete \
  accuracy-compare \
  afg-suggestion \
  chore/audit-safeguards \
  chore/fl-084-validate-checks \
  chore/fl-096-shared-docs \
  claude-md-single-source \
  claude/practical-hypatia-qn8n8g-a1-refresh-gap \
  claude/practical-hypatia-qn8n8g-a2-understat-stale \
  claude/practical-hypatia-qn8n8g-b1-odds-partial \
  claude/practical-hypatia-qn8n8g-b10-docs \
  claude/practical-hypatia-qn8n8g-b14-source-checks \
  claude/practical-hypatia-qn8n8g-b7-one-cs-formula \
  claude/practical-hypatia-qn8n8g-b9-chances-created \
  claude/practical-hypatia-qn8n8g-c2-price-wording \
  claude/practical-hypatia-qn8n8g-c5-private-sync \
  claude/practical-hypatia-qn8n8g-roadmap-fl088 \
  claude/practical-hypatia-qn8n8g-u2-rivals-avg-pts \
  claude/practical-hypatia-qn8n8g-u4-columns-picker \
  claude/practical-hypatia-qn8n8g-u6-vsmodel-contrast \
  feat/centred-cards \
  feat/d5a-journal \
  feat/d5b-reasons \
  feat/d5c-outcomes \
  feat/d5d-summary \
  feat/deadline-snapshots \
  feat/f1a-scoring \
  feat/f1b-pick \
  feat/f1c-head-to-head \
  feat/f1d-vs-model-tab \
  feat/f1e-streak-card \
  feat/f1f-no-saved-forecast \
  feat/home-two-views \
  feat/lineup-styles \
  feat/longer-fixture-horizon \
  feat/move-reason \
  feat/one-confidence-scale \
  feat/plan-expiry \
  feat/planner-strategy-tabs \
  feat/running-scorelines \
  feat/setpiece-tags \
  feat/squad-uplift \
  feat/strategy-risk-budgets \
  feat/transfer-paths \
  fix-live-hits \
  fix-numpy \
  fix/audit-2 \
  fix/benchmark-hindsight \
  fix/data-validity \
  fix/detail-stats-retry \
  fix/dgw-sim-seeds \
  fix/escape-news \
  fix/fl-030-new-signings \
  fix/fl-031-injury-rules \
  fix/fl-054-complete-plan \
  fix/fl-055-replan-captain \
  fix/fl-059-tc-display \
  fix/fl-060-season-end \
  fix/fl-061-hits-all-weeks \
  fix/fl-062-live-ratings \
  fix/fl-063-refresh-push \
  fix/fl-064-live-autosub \
  fix/fl-065-xg-club-then \
  fix/fl-067-return-date \
  fix/fl-068-honest-backtests \
  fix/fl-069-setpiece-history \
  fix/fl-070-picks-per-gw \
  fix/fl-071-absence-snapshot \
  fix/fl-072-missing-inputs \
  fix/fl-073-roll-profit-rule \
  fix/fl-074-four-from-one-club \
  fix/fl-075-shared-planner-settings \
  fix/fl-076-strategy-baseline \
  fix/fl-077-no-chance-flag \
  fix/fl-078-live-points-basis \
  fix/fl-079-gk-saves \
  fix/fl-080-defcon-per-fixture \
  fix/fl-081-return-date \
  fix/fl-082-assumed-defaults \
  fix/fl-083-form-windows \
  fix/fl-085-chips-no-plans \
  fix/fl-086-vice-match-cards \
  fix/fl-087-captaincy-sample \
  fix/fl-091-odds-collector \
  fix/fl-092-upcoming-odds \
  fix/fl-093-returning-players \
  fix/fl-096-workflow-push \
  fix/fl-108-one-recommended-plan \
  fix/fl-109-actual-vs-actual \
  fix/fl-110-profit-vs-roll \
  fix/fl-111-hourly-refresh \
  fix/fl-112-odds-one-row \
  fix/fl-113-recent-priors \
  fix/fl-116-dead-code \
  fix/fl-117-workflows \
  fix/fl-118-skip-duplicate-solves \
  fix/fl-120-protect-news-prices \
  fix/fl-122-tab-strip-scroll \
  fix/fl-123-text-contrast \
  fix/fl-124-tap-targets-aria \
  fix/fl-125-planner-gain \
  fix/fl-126-afg-lean-wording \
  fix/fl-131-xmins-sell-shadow \
  fix/fl-137-bench-all-players \
  fix/fl-138-audit-2-check \
  fix/fl-140-optimiser-silent \
  fix/fl-148-chase-limit-docs \
  fix/fl-152-crowd-history \
  fix/fl-154-accuracy-claims \
  fix/fl-155-shotmap-freshness \
  fix/free-hit-squad \
  fix/journal-start-chance \
  fix/model-log-dates \
  fix/replan-keeps-lineups \
  fix/replan-vice-offline \
  fixes-batch1 \
  fixes-batch2 \
  layout-check-ci \
  leaders-matchday \
  model-bench \
  model-display-parts \
  model-eval-horizons \
  model-sim \
  model-xmins-selling \
  odds-archive-backfill \
  odds-errors \
  odds-names \
  odds-players-fixes \
  player-odds \
  quick-fixes-nav-solver \
  stats-ga-defcon-race \
  test-bench-parts \
  transfer-log \
  ui-redesign \
  ui-round1-type \
  ui-round2-texture \
  weekly-retune \
  xmins-minutes-model \
  xmins-selling-odds \
  xp-table
```
