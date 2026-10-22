# FPL Lab

A personal Fantasy Premier League assistant at **https://afg-design.github.io/FPL-Lab/**.

- **This week:** a deadline checklist covering transfers, lineup, captain, chip and risks.
- **Planner:** tap players to plan transfers over 5 gameweeks, with budget, club limits, free transfers and hits worked out live. Load the optimiser's plans as a starting point.
- **Fixtures, Players, Stats, Chips, Season:** a fixture ticker, a player explorer with price-change progress, underlying form (xGI/90), over- and under-performers, team xG trends, player charts, chip planning and rank history.
- **Model:** how accurate the projections have been this season, plus how they work.

## How it works

| File | What it does |
| --- | --- |
| `fplmodel.py` | Projection model: team ratings from xG, minutes, per-90 rates blended with last season, FPL scoring, calibration |
| `optimise.py` | Multi-gameweek transfer optimiser (integer programme, CBC via PuLP) |
| `backtest.py` / `tune.py` | Re-projects past gameweeks to measure and tune the model |
| `make_priors.py` | Downloads every player's previous seasons into `priors.json` (weekly workflow) |
| `build.py` | Fetches the FPL API, runs everything and writes `site/data.json` |
| `site/index.html` | The dashboard |

`.github/workflows/refresh.yml` rebuilds and publishes every 30 minutes. `priors.yml` refreshes `priors.json` every Monday.

## Settings

- **Team ID:** repository variable `FPL_TEAM_ID` (Settings → Secrets and variables → Actions → Variables). Default 8122679.
- **Refresh now:** Actions → "Refresh FPL data" → Run workflow, or the button on the dashboard.

## Run locally

```
pip install -r requirements.txt
python3 build.py 8122679 site/data.json
cd site && python3 -m http.server 8000
```
