# AGENTS.md

All build rules for this repo live in **CLAUDE.md**. Read it in full before making any
change and follow it exactly. If anything in this file, a prompt or a task description
conflicts with CLAUDE.md, CLAUDE.md wins. Don't add rules here; propose them as a PR
to CLAUDE.md.

## Working alongside Claude Code
- This repo is also worked on by Claude Code. One backlog item = one branch = one PR.
- Branches: `fix/fl-nnn-short-name` or `feat/fl-nnn-short-name`. PR title: `FL-nnn: ...`.
- If a branch for the item already exists, stop and ask; don't start a parallel one.
- Model experiments are logged in `docs/model-log.md`. Check it before proposing a model
  change, and add results there in the existing format.

## Review guidelines
- Treat as P0: anything that could lose or overwrite write-once files in `history/`;
  anything that lets backtests see information not available at the deadline (hindsight).
- Treat as P1: Balanced or Play safe producing a hit; plans that break FPL rules
  (budget, 3-per-club, formation, free-transfer cap of 5); validate.py checks that can't fail;
  UI text stating a figure the data doesn't contain.
- Model changes: the evidence and the adopt/don't-adopt decision rule are in CLAUDE.md
  ("Model changes"), the only version of that rule. Flag any PR that changes projections
  without that evidence or without saying which row of the decision table it falls into.
