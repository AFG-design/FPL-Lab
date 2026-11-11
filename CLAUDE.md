# Working rules for FPL LAB

This file is the single source of truth for how FPL LAB is built. Any other instructions (claude.ai project,
memory) point here; if they disagree, this file wins. When the owner settles a new rule, add it here in the
same PR.

Static site on GitHub Pages (`site/`); `build.py` rebuilds `site/data.json` every 30 minutes (Refresh workflow),
then `validate.py` gates the publish. UK spelling, £, metric. Keep the existing design.

## How to work
- Build on a branch and open a PR for the owner to review. Never merge until the owner says "merge", and don't
  start the next item until the owner says so.
- Only build things that add real value. When asked about a feature, give an honest worth-it verdict first.
- Explain changes plainly in the PR: what was wrong, what changed, what it's worth.

## Data and cost
- No paid data sources or APIs, and no Claude API in the app. Free sources only (public FPL API, Understat,
  football-data.co.uk odds).
- FPL Review is the owner's personal subscription: manual CSV exports for his own use only. Never scrape it,
  commit its data to the repo or publish it on the site.

## Tabs and planner
- AFG suggestion, Model and Data health can be changed, but their tabs stay where they are.
- Planner strategies: Balanced and Play safe never take a hit; only Chase rank may consider a −4. Every
  strategy must always weigh making no moves (rolling the free transfer) and pick it when it's the best option
  that gameweek. No moves for the sake of it, only for a projected net gain.

## Missing, late or ambiguous data
- Every change states what it does when its input is missing, late (e.g. odds not out, status log not saved
  before the deadline) or ambiguous (e.g. two Understat ids, a flag with no chance). Say it in the code comment
  and the PR.
- No silent defaults. Either surface the fallback (mark it `assumed`, as `fplmodel.availability_info` does, and
  show it in the UI) or fail loudly (`validate.py` error, or raise in `build.py`).

## Checks
- New data field or join: add a `validate.py` check where it is cheap (range, sums, one-to-one ids, snapshot used).
  Errors stop the publish; warnings go to the Health page.
- Run `python3 validate.py site/data.json` after a local build, and `npm test` for site JS/CSS.

## Model changes (`fplmodel.py`, params, priors, odds)
This is the only version of the model-change rule (AGENTS.md points here). Model results are logged in
`docs/model-log.md`. Every model change needs both kinds of evidence below in its PR.

**1. Backtest.** Run the backtest before and after, both without and with the status log, and compare segments:

```
python3 backtest.py RAW --json base.json                 # on main (no status log: original behaviour)
python3 backtest.py RAW --status-log --json base_sl.json # as the live build runs
# ...same on the branch -> new.json, new_sl.json
python3 backtest.py --compare base.json new.json
python3 backtest.py --compare base_sl.json new_sl.json
```

Also judge a change on the part it targets, not only on total points: the backtest prints minutes accuracy (start and
60+ chance, expected minutes) and each scoring part on its own (raw, before the final calibration, which can hide a
part that is badly off). `bench.py` prints 5-GW totals (what the planner uses) next to the 1-GW scores; quote both.
A change that helps its own part but not the total is still worth recording in the model log.
Keep a change only if it also holds up on past seasons, not just the current one.

`--compare` flags any segment (position, price band, flagged/unflagged, top 30, GW) with n ≥ 30 where MAE
worsens by more than 0.05 or bias moves by more than 0.2. A change that improves the headline but trips a
segment must be called out in the PR, with the numbers. Put the before/after table in the PR.

**2. Bench.** Run `bench.py` on all three seasons (this season, 2025/26 and 2024/25) and put in the PR description the
paired bootstrap 95% confidence intervals for the difference against main, plus the 5-GW and 1-GW totals for each
season.

**Decision.** "CI" is the paired bootstrap 95% interval from `bench.py`; "segment worse" means `--compare` flagged a
segment. Every model PR must say which row it falls into.

| Result | Decision |
|---|---|
| CI above zero and no segment worse | Adopt. |
| CI includes zero, the change fixes a known error, and no segment worse | Adopt as Marginal: log it in `docs/model-log.md` and re-check later. |
| CI includes zero and the change is only a tweak | Don't adopt. Log the result in `docs/model-log.md`. |
| Any segment trips `--compare` | Don't adopt until it is fixed or explained. |

## UI wording
- Text that asserts a fact ("out", "tonight", "starts", "injured") must test the same condition the data uses
  (`status`, `news`, `chance`, the price threshold), not a proxy.
- Every number shown is labelled for what it is (xP for next GW vs over N GWs, start chance vs real starts,
  projected vs actual).

## Testing
- Check the page at ~390px and ~1280px wide, in both dark and light mode. `npm run layout` (scripts/layout_check.py) opens every screen at
  both widths and fails on JS errors, error cards, sideways page scroll or missing site files; the Check site
  workflow runs it on every PR and keeps the screenshots as an artifact. `scripts/screenshots.py` is for the
  README shots.

## GitHub
- `gh pr create` fails in these sessions (GraphQL blocked). Open PRs with the REST API:
  `gh api repos/AFG-design/fpl-lab/pulls -f title=... -f head=BRANCH -f base=main -f body=...`
- Never merge without the owner's say-so.
