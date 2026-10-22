# FPL Lab

A personal Fantasy Premier League assistant: projected points for every player over the next six gameweeks, best XI and captain, a transfer plan, a fixture ticker, a chip planner, price-change watch and season history.

## How it works

- `build.py` pulls the public FPL API, runs the projection model and writes `site/data.json`.
- `.github/workflows/refresh.yml` runs it every 30 minutes and publishes `site/` to GitHub Pages.
- `site/index.html` is the dashboard. It reloads new data by itself while open.

## Settings

- **Team ID:** set a repository variable `FPL_TEAM_ID` (Settings → Secrets and variables → Actions → Variables). The default is 8122679.
- **Refresh now:** Actions → "Refresh FPL data" → Run workflow, or the button at the top of the dashboard.
- **Refresh frequency:** edit the `cron` line in the workflow. Times are UTC.

## Run locally

```
python3 build.py 8122679 site/data.json
cd site && python3 -m http.server 8000
```

Then open http://localhost:8000.
