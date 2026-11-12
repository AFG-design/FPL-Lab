# FPL Lab: projection model hallucination audit

Date: 29 Oct 2026. Read-only audit: no model code was changed and nothing was pushed.
Code: AFG-design/fpl-lab at `5d51824` (29 Oct, 12:44 UTC). Ground truth: the live FPL API (bootstrap-static, fixtures, live GW1–8, entry 8122679 history and picks), fetched at about 13:33 UTC.

**How data.json was checked.** The sandbox proxy blocks the live site (`afg-design.github.io` returned 403). The repo doesn't hold `site/data.json` either, because it is gitignored. So I ran `build.py 8122679` from the same commit against the live API, which produced 458 players for GW9. To check that this copy matches what's live, I compared it with `history/proj_gw9.json`, the GW9 projection snapshot that Actions committed at 12:44. All 394 players match except one: Struijk is 0.11 in the snapshot and 0.00 in my rebuild, because his flag changed in between.

---

## Confirmed findings

### C1. High: a "back on" date in FPL's news overrides FPL's own 0% flag. Dorgu's date has already passed.
- **Evidence:** these players are status `i`, with `chance_of_playing_next_round = 0` and `chance_of_playing_this_round = 0`. FPL's `ep_next` is 0.0 for all of them. FPL Lab still gives them points in GW9:

  | Player (id) | FPL news | GW9 kick-off | Lab GW9 xP | Lab xMins |
  |---|---|---|---|---|
  | Dorgu (415, MUN) | "Expected back 25 Oct" (date passed, still flagged 0%) | 31 Oct | **1.57** | 20 |
  | Mendy (586, HUL) | "Expected back 31 Oct" | 31 Oct 15:00 | **2.11** | 43 |
  | Tzolis (557, ARS) | "Expected back 1 Nov" | 1 Nov | **2.09** | 50 |
  | Chavarria (583, CHE) | "Expected back 31 Oct" | 31 Oct | 0.88 | 24 |
  | Bergvall (520, TOT) | "Expected back 31 Oct" | 31 Oct | 0.71 | 12 |

- **Cause:** `fplmodel.py:636-637`. Once the kick-off date is on or after the parsed return date, `availability()` returns **1.0**, ignoring FPL's chance of 0. A stale date (Dorgu) therefore becomes full fitness. A return on match day (Mendy) becomes certain.
- **Impact:** `ok=False` stops the optimiser buying these players (`optimise.py:94`). But xP for the 0% players still shows in the Players and Stats tables, and still counts for anyone who already owns one (starting XI, captain, bench order). None of the user's 15 are affected right now.
- **Fix:** for k=0, cap availability at FPL's chance (`min(c, …)`). Count a return date as "possible" (about 0.5) only in the first week after it, and ignore a return date that has already passed while the flag still shows 0.

### C2. Medium (it would hit the user's goalkeeper if the input order changed): the Understat matcher maps two players to one FPL id and silently drops one
- **Evidence:** Understat 7526 "Martín Zubimendi" and Understat 9676 "David Raya" both score **0.86** against FPL id 1, Raya. Raya's FPL surname is "Raya Martín", so the bonus at `understat.py:159-160` (the surname's last word appears in the Understat name) fires on "Martín". Zubimendi's real FPL entry (id 19) scores 0.859, so Raya wins by 0.001. The output dict is keyed by FPL id (`understat.py:171-177`), so whichever player comes later in Understat's list wins. Today that is Raya, which is correct. The side effect is that Zubimendi (FPL 19) has **no Understat row**: his shots and 0.19 xG are missing. If Understat reorders its list, the user's goalkeeper Raya would show Zubimendi's shot, big-chance and xGChain numbers.
- **Model impact today:** none on xP. `understat_sp` only feeds the model when `sp_match > 0`, and it is 0.0 (`fplmodel.py:46`). The damage is to the UI (player sheet "Shots and chances", Stats set-piece table) and to any future switch-on of `sp_match`.
- **Fix:** assign matches one-to-one, best score first, and reject a pairing when the runner-up is within 0.02. Apply the surname bonus only to the first surname, not to matronymics ("Raya Martín", "Zubimendi Ibáñez").

### C3. Medium: the Understat matcher drops real players without a visible warning
- **Evidence:** players with 300+ FPL minutes and no Understat row:
  - Yéremy Pino (211, CRY, 539 min): Understat "Yeremi Pino" scores 0.709, just under the 0.72 cut-off, so 1.13 xG of shots is lost.
  - Jair Cunha (474, NFO, 534 min): Understat "Jair" scores 0.59.
  - A. Becker (LIV goalkeeper, 720 min).

  `meta.unmatched = 4` appears in `sources`, but no player is marked as missing. The Stats leaderboards and the player sheet leave these players out, as though they had no shots.
- **Cause:** `understat.py:167` (fixed 0.72 cut-off, no list of manual overrides).
- **Fix:** add a small `understat_overrides.json` ({us_id: fpl_id}), and show "no Understat match" on the player sheet when `us` is missing for a player with real minutes.

### C4. Medium: an 'Unknown return date' becomes a made-up recovery curve
- **Evidence:** `fplmodel.py:11,634-635` sets availability to k/6 for "Unknown return date". That turns no information into numbers that look exact:

  | Player | Projected xP, GW10 to GW14 |
  |---|---|
  | Saka | 0.60 → 1.24 → 2.20 → 3.00 → 3.75 |
  | Semenyo | 0 → 0.68 → 1.01 → 1.52 → 1.85 |
  | **João Pedro (user's squad)** | 0.24 → 0.47 → 0.69 → 1.05 → 1.17 |

  Twenty-plus players get this ramp. The UI shows no sign that these are assumed.
- **Fix:** keep the assumption, but mark these GWs in data.json (for example `xp_assumed: true`) and show them in grey or italic. Alternatively, apply the ramp only from the second week onwards.

### C5. Low: the xP breakdown doesn't add up to xP
- **Evidence:** Haaland's GW9 `xp_detail` adds up to 4.73, but his xP is 5.06. `build.py:289,307` hard-codes `slope = 0.86` (a copy of `DEFAULTS["cal_slope"]`) and leaves out the calibration intercept (`cal_int × P(plays)`, 0.33 here). If `cal_slope` is ever re-tuned, the breakdown will silently drift further.
- **Fix:** use `DEFAULTS["cal_slope"]` and add an "appearance adj." line equal to `xp − sum(detail)`.

### C6. Low: the forwards' defensive contribution threshold is read off sparse data and comes out wrong
- **Evidence:** `fplmodel.py:185-197` sets each position's threshold to the smallest count that earned DC points. For FWD only one hit has happened so far (at 16), so `dc_thr["FWD"] = 16`. FPL's rule is 12, the same as MID. The MID threshold comes out at the correct 12.
- **Impact:** a small under-projection for forwards who make a lot of defensive actions.
- **Fix:** take thresholds from the game rules (DEF 10, MID/FWD 12), or pool MID and FWD, and use the data only as a check.

### C7. Low: no market odds for upcoming fixtures
- **Evidence:** `odds/odds.json` (built 12:44 today) has 80 matches, all played, with 0 upcoming. The fixture-level blend `direct_w = 0.85` (`fplmodel.py:361-364`) therefore never applies to GW9+. Only the past-match market ratings are used. This isn't fabrication, but the odds don't drive future fixtures the way the docs suggest. I couldn't fetch `football-data.co.uk/fixtures.csv` (proxy 403) to tell whether the source had no rows yet or the matching failed.
- **Fix:** surface "upcoming odds: 0" as a warning in the Health view when the next GW has no market rows.

---

## Suspected findings (the mechanism is confirmed; the effect needs judgement)

### S1. Medium (user's squad): Gibbs-White's missed GW7 is treated as being dropped
- **Evidence:** Gibbs-White (480) started GW1–6 and GW8 (90 minutes each) and played 0 minutes in GW7. FPL posted news about him on 16 Oct, just before the GW7 deadline, and it has since cleared. `news_absences()` only looks at the **latest** finished GW (`fplmodel.py:139`, `k = max(...)`). The status log only starts at GW8 (`history/status.json` holds GWs 8 and 9). So GW7 counts as a non-start.
- **Result:** `p_start` 0.76, xMins 68, GW9 xP 3.05. With a near-certain start he would project at roughly 3.8–4.0.
- **Impact on the user:** the recommended line-up puts him on the bench (bench order: Dubravka, Gibbs-White, Calafiori, João Pedro). The "best" plan sells him (out: 8, 165, 175, 480).
- **Fix:** let `news_absences` look back over every GW since the status log began, not only the latest one. Or backfill `status.json` for GW1–7 from the archived `proj_gw*.json` snapshots, which hold status and chance.

### S2. Medium (user's squad): Conference League congestion for Brighton uses dates the file admits it assumed
- **Evidence:** `europe.json` marks UECL as `"confirmed": false`, with dates "assumed to match Europa League Thursdays". Brighton GW10 and GW12 still get the 0.93 start-chance multiplier (`build.py:133`), and the UI states "UECL Thu 05 Nov" as fact. This affects the user's De Cuyper (115) and Groß (124). The xP effect is small (about −0.1 to −0.2 per GW).
- **Fix:** skip congestion when a competition has `confirmed: false`, or label it "unconfirmed" in the UI. Also check that Brighton really are in the 2026/27 UECL.

### S3. Low: off-by-one risk in "Suspended until"
- **Evidence:** "Suspended until 7 Nov" makes a player fully available for a 7 Nov kick-off (`kickoff < ret` is false). Bentancur and Sessegnon (GW10, 7 Nov) and Yarmoliuk ("until 8 Nov", GW10 on 8 Nov) each get about 1.5–1.7 xP in GW10. Whether FPL's date means "available from" or "banned through" needs checking against one past case.
- **Fix:** check one past case in `history/news.json` and compare with real minutes.

### S4. Low: the default chance for a flagged player is a made-up 50%
- **Evidence:** a non-available player with `chance = None` gets 50% (`fplmodel.py:641-642`). No current player hits this (every non-'a' player has a chance value today).
- **Fix:** show it as "unknown" in the UI, or use 25% for `i`, `s` and `n`.

---

## Calibration (backtest.py ran offline, GW3–8, on API data fetched today)

| | n | MAE | RMSE | corr | bias |
|---|---|---|---|---|---|
| Model (with priors) | 2284 | 1.85 | 2.68 | **0.412** | −0.02 |
| Model (no priors) | 2284 | 1.86 | 2.70 | 0.395 | −0.04 |
| Baseline (last-4 average) | 2284 | 2.11 | 3.05 | 0.295 | +0.08 |

Bias (projected minus actual) by position and price, from a script I wrote on top of `project()`, using the same pool as backtest.py:

| Group | n | Bias |
|---|---|---|
| GKP (all) | 129 | **−0.44** |
| GKP £5.0–6.9m | 60 | **−0.70** |
| DEF | 798 | −0.05 |
| MID | 1088 | +0.01 |
| MID under £5.0m | 250 | +0.21 |
| FWD | 269 | −0.10 |
| £7.0–9.9m (all positions) | 115 | −0.47 |
| £10m+ | 12 | too few to read |

- **Weakest areas:** the lowest bucket is under-projected (xP 0–1: projected 0.52, actual 0.83). The top-30 picks are over-projected in 4 of 6 GWs (GW3 +0.78, GW6 +0.76, GW8 +0.58; mean +0.31). The top of the table is where transfer and captain calls are made.
- **Goalkeepers** are systematically under-projected. Raya (user's) is likely 0.3–0.7 short.
- **Caveats:** the backtest uses today's bootstrap (current team, position and price, and hindsight injury news through `out_weeks(hindsight=True)` for minutes). That flatters the minutes model slightly. backtest.py's `__main__` also passes no `status_log`.

---

## User's squad (8122679, BACK2BACK, GW8 picks; matches the API)

| Player | Finding |
|---|---|
| Raya (1) | Understat collision (C2), currently correct. Goalkeeper under-projection bias (−0.44). |
| Calafiori (8) | Flagged 75%, xP 1.69. Consistent: p_start 0.39 after 22 minutes in GW8. OK. |
| Gibbs-White (480) | **S1**: likely under-projected. Benched and sold by the plan because of it. |
| De Cuyper (115), Groß (124) | **S2**: congestion from unconfirmed Conference League dates. |
| João Pedro (165) | **C4**: invented recovery ramp (0.24 → 1.17 by GW14). Status `i`, unknown return. |
| Dubravka (497) | 0 xP, 0 xMins (backup goalkeeper). Correct. |
| Konsa, Muharemović, Rogers, Palmer, Haaland, Calvert-Lewin, Slater, van Ewijk | No issues found. |

Free transfers (4), bank (£0.8m) and squad ids match the API history and picks.

---

## Checked and clean
- **Grounding:** all 458 players in data.json exist in bootstrap-static with matching id, name, team, position and price (`now_cost/10`). 0 mismatches.
- **Gameweek:** meta shows cur_gw 8 and next_gw 9 with deadline 31 Oct 11:00, which matches the API.
- **Freshness of source files (repo):** odds and Understat built 29 Oct 12:44 UTC, priors 26 Oct, player odds 28 Oct, crowd 23 Oct (GW8, once per GW, as designed).
- **Fixtures:** every team's opponent and home/away for GW9–14 match /api/fixtures/. There are no blanks or doubles in GW9–14, no unscheduled fixtures, and no xP for teams without a fixture.
- **Impossible values:** no negative xP, NaN or null xP. The maximum single-GW xP is 5.51 (Gabriel, GW10). Every probability (p_start, psub, dc_rate, dist p10/p6/blank) is within 0–1, and p_start + psub ≤ 1. The distribution percentiles are in order. Every player with xP has a distribution. xMins ≤ 90.
- **Unavailable (`u`) players:** none has xP. Players flagged 75% (`d`) carry about 75% of their usual xP, which is consistent.
- **Optimiser:** no player marked `ok=False` is bought in any of the 15 plans or placed in the recommended XI.
- **Odds team mapping:** every team name was matched (`unmatched_names` is empty), and the four Understat code aliases (BRI, FLH, LED, NOT) cover all 20 clubs this season, including Coventry, Hull and Ipswich.
- **Player odds:** 5 unmatched names, all fringe or academy players. The player odds feed only the Health page, not xP.
- **Understat:** no Understat id maps to two FPL ids. All 446 other matches have correct teams. The low-score matches I spot-checked (Solanke, Buendía, Gannon-Doak/Doak, Cuenca and others) are correct.

## Couldn't check
- **Live data.json on GitHub Pages:** proxy 403. I used a local rebuild from the same commit instead, cross-checked against the committed snapshot (see the top).
- **football-data.co.uk:** proxy 403, so I couldn't confirm why `odds.json` has no upcoming matches (C7).
- **GitHub Actions run history (`gh run list`):** 403, because the repo isn't attached with API access. So I couldn't confirm the 30-minute refresh is succeeding.
- **Browser UI rendering at phone and desktop widths:** no browser was used. I checked the code paths only (for example `players.js:48` shows `chance ?? 0`, and `p.us` is guarded where it is used).
