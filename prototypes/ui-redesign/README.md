# UI redesign prototypes (not part of the app)

Three visual directions for FPL LAB, built as isolated static prototypes so the owner can compare them before any
change is made to the real site. **Nothing here is loaded by `site/`, `build.py`, the workflows or GitHub Pages**
(Pages publishes `site/` only). The prototypes read `site/vendor/fonts` and `site/badges` read-only by relative path.

| Folder | Concept |
|---|---|
| `a-refined/` | A · Refined: the current design with tighter spacing, one type scale, a one-row header and the team above the fold |
| `b-analytics/` | B · Premium Analytics: graphite surfaces, a decision board, xP heat grids, a master-detail player panel and charts |
| `c-interactive/` | C · Modern & Interactive: a rail and dock, an interactive pitch (strategy switch and GW scrubber), cards and sheets |
| `compare.html` | Side-by-side board: current site vs A/B/C, desktop and phone, plus the scorecard and recommendation |
| `screenshots/` | Rendered shots (WebP). `current--*` are the live site; the rest come from `shoot.py` |

Each prototype has five screens: `#home`, `#planner`, `#players`, `#players/411` (player detail), `#fixtures` and
`#rivals`. Add `?theme=light` for light mode.

## Data

`shared/sample-data.js` is a **sample**: a trimmed copy of the published `data.json` from 18 Nov 2026 09:02 (GW11,
public FPL API data only, no FPL Review data). Mini-league managers are anonymised ("Rival A", "Sample FC 3"). Every
prototype shows a "sample data snapshot, not live" strip. A few lines of copy (the lineup tip, "81% of managers near
your rank") are taken word for word from the live site's text in that snapshot.

To refresh it from a newer build:

```bash
python3 prototypes/ui-redesign/shared/extract.py site/data.json
```

`extract.py` fails loudly if a field it needs is missing. It has no silent defaults.

## Run and screenshot

```bash
python3 -m http.server 8000      # from the repo root, then open /prototypes/ui-redesign/compare.html
python3 prototypes/ui-redesign/shoot.py
```

`shoot.py` opens every screen at 390×844 and 1440×900, in dark mode (and light for home and players). It exits 1 on
any JavaScript error, failed local request or sideways page scroll.

## Known gaps

- None of the prototypes include the live player sheet's "Why 4.7 xP" breakdown. A real build must keep it.
- Not prototyped: Deadlines, Chips, Review, You vs the model, Model, Data health, FPL School, AFG and live matchday states.
- C's fixtures view shows only the first match of a double gameweek, and badges without team names on phones.
- Buttons such as Compare, Add to plan and Filters are visual only.
