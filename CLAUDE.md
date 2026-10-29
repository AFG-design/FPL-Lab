# Working rules for FPL LAB

Static site on GitHub Pages (`site/`); `build.py` rebuilds `site/data.json` every 30 minutes (Refresh workflow),
then `validate.py` gates the publish. UK spelling, £, metric. Keep the existing design.

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
Run the backtest before and after, both without and with the status log, and compare segments:

```
python3 backtest.py RAW --json base.json                 # on main (no status log: original behaviour)
python3 backtest.py RAW --status-log --json base_sl.json # as the live build runs
# ...same on the branch -> new.json, new_sl.json
python3 backtest.py --compare base.json new.json
python3 backtest.py --compare base_sl.json new_sl.json
```

`--compare` flags any segment (position, price band, flagged/unflagged, top 30, GW) with n ≥ 30 where MAE
worsens by more than 0.05 or bias moves by more than 0.2. A change that improves the headline but trips a
segment must be called out in the PR, with the numbers. Put the before/after table in the PR.

## UI wording
- Text that asserts a fact ("out", "tonight", "starts", "injured") must test the same condition the data uses
  (`status`, `news`, `chance`, the price threshold), not a proxy.
- Every number shown is labelled for what it is (xP for next GW vs over N GWs, start chance vs real starts,
  projected vs actual).

## Testing
- Check the page at ~390px and ~1280px wide (`npm run dev`; `scripts/screenshots.py` for the README shots).

## GitHub
- `gh pr create` fails in these sessions (GraphQL blocked). Open PRs with the REST API:
  `gh api repos/AFG-design/fpl-lab/pulls -f title=... -f head=BRANCH -f base=main -f body=...`
- Never merge without the owner's say-so.
