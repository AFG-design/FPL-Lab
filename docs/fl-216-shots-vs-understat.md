# FL-216: Comparing Bzzoiro Sports Data set-piece xG with Understat

Analysis only (no model or pipeline change). Compares `2026/27` shot-level set-piece xG from **FPL-Core-Insights (olbauday), test data only** (`data/2026-2027/By Gameweek/GW1..10/shots.csv`, sourced from Bzzoiro Sports Data; downloaded at run time into git-ignored `archive/fpl-core-insights/`, never committed) against FPL Lab's Understat data (`understat/fpl_players.json` and `site/shots.json`, currently **89 of 100 finished matches**, last updated 1 Nov 2026).

## 1. Set-piece xG comparison (2026/27)

Understat labels shots `O` (open play), `P` (penalty), `C` (corner), `S` (set piece), `F` (direct free kick) — FPL Lab counts `C + S + F` (`599` shots, `59.78` total xG across 89 matches).
Bzzoiro labels shots `assisted`, `regular`, `fast-break`, `penalty`, `corner`, `free-kick`, `set-piece`, and `throw-in-set-piece`.

### Same-window comparison (GW1–9: Understat 89 matches vs Bzzoiro 90 matches)

| Slice | Players (union / both / US-only / BZ-only) | Player corr (union) | Player corr (both) | Player mean diff (BZ − US) | Team corr (`n = 20`) | Team mean diff (BZ − US) | Total SP xG (BZ vs US) |
|---|---|---|---|---|---|---|---|
| **Excl. `throw-in-set-piece`** (`corner` + `free-kick` + `set-piece`) | 253 / 224 / 25 / 4 | **0.7646** | **0.8694** | `−0.0413` | **0.7676** | `−0.5636` | `48.51` vs `59.78` |
| **Incl. `throw-in-set-piece`** | 273 / 224 / 25 / 24 | **0.7160** | **0.8274** | `−0.0058` | **0.6416** | `−0.0798` | `58.18` vs `59.78` |
| **All shots (all situations, GW1–9)** | 368 union | **0.8917** | — | — | — | — | — |

### Full GW1–10 comparison (including 11 matches Understat is missing)

- **Per player** (`n = 276` union, `224` both, `25` Understat-only, `27` Bzzoiro-only): `r = 0.6700` (`0.7747` on shared players), mean diff `+0.0226` xG (`66.01` vs `59.78`), MAE `0.1462`.
- **Per team** (`n = 20`): `r = 0.5920`, mean diff `+0.3113` xG, MAE `0.8354`.

### Missing shots & players (the main discrepancy)

- In GW1–9, **276 of 2,466 Bzzoiro shots (11.2%)** — including **70 set-piece shots** — have a **blank `player_id` and blank `player_name`** in the FPL-Core-Insights export (GW1–10: **314 of 2,738 = 11.5%**, `81` set-piece shots).
- That gap causes **25 players** with Understat set-piece xG to show `0.0` in Bzzoiro and pulls some teams down sharply (e.g. Arsenal `3.64` in Understat vs `1.57` in Bzzoiro).
- Where players *are* mapped in both sources, correlation is strong (`r = 0.8694` excluding throw-ins; `r = 0.8917` across all shots).

## 2. Bzzoiro Sports Data: terms of use & xG provenance

- **Service:** [Bzzoiro Sports Data (BSD)](https://sports.bzzoiro.com/) (`© 2026 Bzzoiro LLC`), an indie-developer sports API launched around Feb 2026 ([r/sportsanalytics launch thread](https://www.reddit.com/r/sportsanalytics/comments/1qz4mku/i_built_a_free_football_data_ml_prediction_api_as/)).
- **Pricing & limits:** Football endpoints are **free** with a registered API token (7,500 requests/day, ~25 req/s burst; other sports require a paid $7/mo add-on, per [AnythingMCP's Bzzoiro connector docs](https://anythingmcp.com/guides/bzzoiro-to-mcp)).
- **Terms of Service & Data licence:** The homepage footer links to `Terms of Service` and `Data licence`, but those legal pages were not publicly crawlable from this environment (`sports.bzzoiro.com/terms/` and `/data-licence/` could not be fetched). **Public redistribution terms (publishing derived files to GitHub / GitHub Pages) are therefore unverified.**
- **Where its xG comes from:** Not publicly documented. The developer's Reddit post describes a CatBoost model for match predictions, while the shot-map payload exposes `xg`, `xgot`, pitch coordinates and `goal_mouth_*` fields (similar to Sofascore/Opta schemas) without naming the upstream event-data vendor or shot-xG methodology.

## 3. Verdict

**No — not as-is.** Technically, Bzzoiro's xG agrees closely enough with Understat on mapped players (`r = 0.87` set-piece, `r = 0.89` all shots) and stays up to date when Understat stalls. However, it should **not** stand in for Understat yet unless two conditions are cleared first:

1. **Legal / licence check:** read Bzzoiro's `Data licence` and `Terms of Service` on [sports.bzzoiro.com](https://sports.bzzoiro.com/) to confirm free public-site redistribution is permitted, and use a direct `BZZOIRO_API_KEY` (not FPL-Core-Insights).
2. **Player-ID completeness:** verify directly against Bzzoiro's API that the ~11.2% blank `player_id` shots are an FPL-Core-Insights mapping drop rather than missing in Bzzoiro itself — losing 11% of shots (and half of Arsenal's set-piece xG) would distort FPL Lab's set-piece table and shot maps.
