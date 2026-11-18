---
name: verify
description: Check FPL LAB works end to end before opening a PR: fresh data.json build for team 8122679 plus validate.py, npm test, every screen in a headless browser at 390px and 1280px (no JS errors or error cards), and the homepage squad (15 players, sensible team value and bank). Prints a PASS/FAIL summary naming the failing step. Use before every PR (CLAUDE.md, Verification), after any change to build.py, the model, the planner or site/, or when asked to "verify", "check it works" or "run the checks".
---

# Verify FPL LAB

One command, about 2 minutes (the build is ~60 s of it):

```
python3 scripts/verify.py            # or: npm run verify
```

It runs, reusing the repo's own checks rather than copies of them:

| Step | What | Fails when |
|---|---|---|
| build | `python3 build.py 8122679 site/data.json` (beside `npm test`) | the FPL API is unreachable or build.py raises |
| npm test | lint, whole-app check, node tests | any lint error or failing test |
| validate | `python3 validate.py site/data.json` | any validate error (warnings are printed, not failed) |
| screens | `scripts/layout_check.py`: every view at 390px and 1280px | a JS error, an error card, sideways page scroll, a missing site file |
| squad | homepage, Current GW and Next GW views, both widths | not 15 players on pitch and bench; team value not £80.0m-£120.0m, or (Current GW) not today's prices of the squad; bank not £0.0m-£30.0m, or (Current GW) not `manager.bank` |

Options: `--no-build` reuses the current `site/data.json` (for a site-only change, ~50 s); `--team ID` for another team.

## How to use the result

- The last block is the summary: one `PASS`/`FAIL` line per step, then `PASS` or `FAIL: ... failing step: <name>`.
  Failing steps print their last 40 lines of output above it. Put the summary in the PR description.
- Exit code 0 only when every step passes.
- If a step fails, fix the cause. Don't skip, retry, add a sleep or loosen a check to make it pass, and don't edit the
  check that judges your change unless the PR explains why it was wrong (CLAUDE.md, Verification). After 3 failed fix
  rounds on the same failure, stop and escalate with what you tried.
- `build` failing with a network error means the FPL API is down or blocked here, not that the code is wrong: say so
  in the PR rather than reporting a pass. The later steps show `SKIP` (not run).
- build.py writes to `history/` as a side effect. verify.py puts back the files it changed there (only ones that were
  clean before the run) and removes ones it created, and says which. Never commit `history/` from a local build.

## What it doesn't cover

Python unit tests (`python3 -m unittest discover tests`, ~90 s) and the slower browser checks CI runs
(`contrast_check.py`, `tap_check.py`, `players_check.py`, `rivals_check.py`, `behaviour_check.py`). Run the unit tests
before every PR as well; run the others when your change touches what they check. Model changes still need the
backtest and bench evidence in CLAUDE.md.
