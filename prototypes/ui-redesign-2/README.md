# UI redesign prototypes, round 2 (not part of the app)

Three visual directions for FPL LAB, built after the second visual audit (18 Nov 2026, GW11) as isolated static
prototypes, so the owner can compare them before any change is made to the real site. **Nothing here is loaded by
`site/`, `build.py`, the workflows or GitHub Pages** (Pages publishes `site/` only). The prototypes read
`site/vendor/fonts` and `site/badges` read-only by relative path and make no other requests (`shoot.py` fails on any
non-local request). Round 1 (`../ui-redesign/`) is frozen and kept as a record.

| Folder | Concept |
|---|---|
| `a-refined/` | A · Refined: today's tokens and layout with the audit-2 fixes, one `<h1>` per view, one type scale, a 113px phone header |
| `b-analytics/` | B · Premium Analytics: hairline panels, KPI ribbon, decision board, squad xP matrix, screener with a detail panel, calibration chart |
| `c-interactive/` | C · Modern & Interactive: 3-step decisions (captain choice updates pitch and total), GW scrubber, "/" palette, compare tray, tabbed sheet |
| `compare.html` | Comparison board: today's site vs A/B/C, desktop and phone, audit coverage, measured scorecard, recommendation |
| `screenshots/` | WebP shots. `current--*` are the live site (18 Nov 17:02 data, served from a local copy of `site/`); the rest come from `shoot.py` |
| `measurements.json` | Output of `measure.py`: phone header height, text under 11px, AA contrast, controls under 24px |

Screens in each prototype: `#home`, `#planner`, `#players`, `#players/411` (player detail), `#fixtures`, `#rivals`,
`#model`, `#model/health`. Add `?theme=light` for light mode; C also takes `?state=palette` and `?state=compare`.

## Data

`shared/sample-data.js` is a **sample**: a trimmed copy of the published `data.json` + `data-extra.json` from
18 Nov 2026 17:02 (public FPL API data as `build.py` joins it; no FPL Review data). Mini-league managers are anonymised
("Rival A", "Sample FC 3"). Every prototype shows a "sample data" strip. Refresh it from a newer build with:

```bash
python3 -I prototypes/ui-redesign-2/shared/extract.py PATH/data.json PATH/data-extra.json
```

`extract.py` fails loudly if a field it needs is missing. A player with no extra detail gets `detail: null`, and the
prototypes say "No breakdown" rather than showing zeros.

## Run, screenshot, measure

```bash
python3 -m http.server 8000      # from the repo root, then open /prototypes/ui-redesign-2/compare.html
python3 prototypes/ui-redesign-2/shoot.py
python3 prototypes/ui-redesign-2/measure.py [COPY_OF_SITE_WITH_DATA]
```

## Known gaps

- Not prototyped: Deadlines, AFG suggestion, FPL School, Chips, Review, You vs the model, Stats, xP table, live matchday.
- Shirts are replaced by club crests (shirts load from FPL's servers). White crests need a backing tile in light mode.
- Rivals' pin toggle is shown only in A. Buttons such as Compare with model, Refresh and Add filter are visual only.
- Headless Chromium only; not checked on a real phone, in Safari or with a screen reader.
