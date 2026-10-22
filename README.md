# FPL Lab

A personal Fantasy Premier League assistant at **https://afg-design.github.io/FPL-Lab/**.

- **This week:** a deadline checklist covering transfers, lineup, captain, chip and risks, each with a plain verdict (Strong, Marginal, Coin flip) and details on tap. A strategy switch picks Balanced, Play safe (track the managers around your rank) or Chase rank (differentials).
- **Planner:** tap a player to make him captain or vice, bench or start him, lock him or replace him. **Re-plan** runs the optimiser in your browser (HiGHS, in `site/vendor/`) with your locks, bans, captains and hit limit.
- **Planner (moves):** tap players to plan transfers over 5 gameweeks, with budget, club limits, free transfers and hits worked out live. Load the optimiser's plans as a starting point.
- **Rivals:** what the top 10k and managers around your rank own and captain, the biggest threats and your differentials, and your mini-leagues with a rival-by-rival comparison.
- **Fixtures, Players, Stats, Chips, Season:** a fixture ticker, a player explorer with price-change progress, underlying form (xGI/90), over- and under-performers, team xG trends, player charts, chip planning and rank history.
- **Review:** each gameweek's captain, bench, transfers and model check, plus season totals and your best and worst transfers.
- **Install and sync:** add it to your home screen; plans sync between devices through a `sync` branch (needs a fine-grained token with Contents read/write on this repo).
- **Model:** how accurate the projections have been this season, plus how they work.

## How it works

| File | What it does |
| --- | --- |
| `fplmodel.py` | Projection model: team ratings from xG, minutes, per-90 rates blended with last season, FPL scoring, calibration |
| `optimise.py` | Multi-gameweek transfer optimiser (integer programme, CBC via PuLP) |
| `backtest.py` / `tune.py` | Re-projects past gameweeks to measure and tune the model |
| `crowd.py` | Samples 2,000 top-10k teams, 500 around your rank and your mini-league rivals once per gameweek into `crowd/latest.json` |
| `europe.json` | European fixtures used to flag rotation risk. Edit if dates change |
| `understat.py` | Shots, shots in the box, big chances (xG ≥ 0.3) and chances created from Understat, cached per match in `understat/` (workflow every 3 hours) |
| `site/plan-solver.js` | The browser version of the optimiser |
| `make_priors.py` | Downloads every player's previous seasons into `priors.json` (weekly workflow) |
| `build.py` | Fetches the FPL API, runs everything and writes `site/data.json` |
| `site/index.html` | The dashboard |

`.github/workflows/refresh.yml` rebuilds and publishes every 30 minutes. `priors.yml` refreshes `priors.json` every Monday. `crowd.yml` checks every 20 minutes and samples other managers' teams once per gameweek, just after the deadline.

## Settings

- **Team ID:** repository variable `FPL_TEAM_ID` (Settings → Secrets and variables → Actions → Variables). Default 8122679.
- **Refresh now:** Actions → "Refresh FPL data" → Run workflow, or the button on the dashboard.

## Run locally

```
pip install -r requirements.txt
python3 build.py 8122679 site/data.json
cd site && python3 -m http.server 8000
```
