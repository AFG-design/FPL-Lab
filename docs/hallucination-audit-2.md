# FPL Lab: second hallucination audit

Date: 29 Oct 2026. This audit was read-only: no code was changed, nothing was pushed and no PRs were opened.

**What I tested against**
- **Code:** `origin/main` at `e9e808e` ("Data update"). That is PR #19 (`1ed7f29`) plus one data commit.
- **Build:** a fresh `build.py 8122679`, run in a scratch copy at `/tmp/claude-0/-home-claude/fc363e4d-54d2-50a5-86e1-b07d0ede8d0b/scratchpad/run2`. It built 458 players for GW9.
- **Validator:** `validate.py` passed with **0 errors and 1 warning** (no GW9 odds).
- **Ground truth:** the live FPL API, fetched today. It covered bootstrap-static, fixtures, live GW1–8, and for entry 8122679: entry, history, transfers and GW8 picks. It also covered element-summary for six players.

---

## PR #19 fixes: they hold on today's data
- **0% flags:** no player at 0% has GW9 xP above 0. The highest is 0.00. Dorgu (415) has GW9 0.00, and his GW10–14 ramp is marked `assumed`. Mendy (586) is now fit (100%).
- **Understat:** Raya (1) maps to 9676 and Zubimendi (19) to 7526, which are distinct. The overrides cover Pino (211) and Cunha (474). No player with 300+ minutes is unmatched.
- **xp_detail:** checked by the validator, with 0 errors. It now has an `appear_adj` line.
- **Gibbs-White (480):** p_start is 1.00, with GW9 xP 4.02. The cleared-news absence rule now checks every finished GW.
- **UECL:** skipped as `confirmed:false`. Brighton fixtures carry no `eu` flag, and the week strip says "UECL (dates unconfirmed)".
- **DC thresholds:** come from the rules (`DC_THR`).
- **No GW9 odds:** this now shows as a Health warning.

---

## New findings

### N1. High: an injury reported after the deadline is read as "lost his place". Affects João Pedro (user's squad) and 6 others. Mechanism confirmed; size estimated.
- **Mechanism:** `out_weeks()` (`fplmodel.py:109-130`) counts a GW as "out" only in two cases:
  - the status was saved at that GW's deadline, or
  - the deadline came after `news_added`.

  `news_absences()` (`fplmodel.py:133-170`) only looks at players whose status is now `a`. So a player who gets injured between the GW8 deadline (23 Oct 17:30) and his GW8 match, and is still flagged, has his GW8 0 minutes treated as being dropped. His recency-weighted start chance then collapses.
- **Evidence:** I added GW8 to `out` for these players to see what changes (`a2/flagged.py` in the scratchpad):

  | Player (id) | Flag now (news_added) | p_start (now → if GW8 counted as injury) | GW9 xP | GW9–14 xP |
  |---|---|---|---|---|
  | **João Pedro (165, user's)** | i 0%, "Unknown return date" (24 Oct 16:30, at kick-off) | 0.35 → 0.90 | 0 → 0 | **3.6 → 8.8** |
  | Grealish (238) | d 75% (24 Oct 14:30) | 0.38 → 0.95 | 0.98 → 1.84 | 7.2 → 17.0 |
  | L. Miley (459) | d 75% (27 Oct) | 0.39 → 1.00 | 0.93 → 1.74 | 6.6 → 15.7 |
  | Strand Larsen (222) | d 75% (23 Oct 17:00) | 0.39 → 0.98 | 0.89 → 1.76 | 6.7 → 16.1 |
  | Timber (644), Matheus N. (389), Fernandez-Pardo (634) | d 75% at the GW8 deadline too | about 0.39 → 1.0 | about halved | about halved |

- **Caveat:** for a fully fit player who misses a game with no news, about 0.39 is realistic. Of 82 such cases in GW3–8, 37% started the next game. But for players FPL has since flagged, the injury explains the absence. They also get the ×0.75 flag cut, so they are penalised twice.
- **Impact on the user:** João Pedro's recovery ramp (from the first audit, C4) is scaled by the wrong p_start of 0.35, so his GW10–14 xP is roughly 2.4× too low. Every plan sells him in GW9 or GW10. Selling may still be right, since his return date is unknown, but the numbers behind it are wrong.
- **Fix:** in `out_weeks`, also count GW *k* as out when the player is flagged now and his `news_added` falls between deadline *k* and the end of GW *k*. Count a `d` flag of 75% or less at a deadline as "doubtful", not "dropped".

### N2. Medium: "missed his club's last game with no injury news" shown next to an injury flag. Confirmed.
- **Where:** `player-sheet.js:51`. The sentence fires on `!p.ret && last 0 minutes && 2+ of the last 4 played`. It never checks `status` or `news`.
- **Evidence:** it fires for 38 players today. 10 of them are flagged. Examples:
  - **João Pedro (165)**: "Thigh injury – Unknown return date"
  - Sarr (208): i 0%, "Expected back 8 Nov"
  - Grealish (238), Matheus N. (389), Strand Larsen (222), Miley (459), Timber (644), Fernandez-Pardo (634), Isidor (553), Rashford (429)

  On the same sheet, `minutes` also prints "FPL lists him at 0%: Thigh injury…". So one panel contradicts itself.
- **Fix:** only show this sentence when `status === "a" && !news`. Otherwise show "He missed his club's last game (FPL news since: …)".

### N3. Medium: "He has started about 39% of recent games" and the "Starts" tile misstate p_start. Confirmed. Affects Calafiori (user's squad).
- **Where:** `player-sheet.js:52` and the `Starts` tile at `player-sheet.js:120`. Both print `p_start`, which is a start chance weighted by recency with `min_recency 0.4`, so the last game carries about 60% of the weight. It is not a share of recent games.
- **Evidence:** 16 players show a number at least 30 points below their real starts in the last 5 GWs:
  - 11 players show "39%" but started 4 of their last 5: Solanke, Wissa, Buendía, Havertz, Okafor, Anthony, Thiaw, Berge, Martinez, Stach and **Calafiori (8)**.
  - Calafiori started GW1–7 and came on for 22 minutes in GW8.
  - Cunha shows 15% but started 3 of 5.
- **Related (suspected, user's squad):** Calafiori was flagged 75% ("Hip injury", posted 24 Oct 18:30, after Arsenal's 14:00 kick-off). His GW8 sub appearance is probably injury-related. Instead it is read as rotation (p_start 0.39, nailed 30) **and** cut by the 75% flag. The result is GW9 xP 1.69, and every plan sells him in GW9.
- **Fix:** relabel as "Chance to start next game", or print the real count ("started 4 of his last 5"). For N1-type cases, see the N1 fix.

### N4. Medium: "may rise or fall tonight" alerts fire in bands where the app's own record shows no price change ever followed. Confirmed.
- **Source:** price projections come from FPL's own `price_change_projections` field. That is real data, which is fine. `history/prices.json` covers 7 nights. Its track record, also shown in the UI, is:
  - 100%+ band: 19/20 rises and 45/46 falls happened.
  - 90–100% band: 0/13 rises and 0/90 falls.
  - 75–90% band: 0/31 rises and 0/169 falls.
- **The problem:** the following all fire anywhere from 75% or 80% upwards, below the 100% threshold where the record says changes actually happen:
  - "Likely to rise/fall" tables at ≥75 (`stats.js:175-176`)
  - moves-summary "may rise tonight: do this first" at ≥75 (`moves-summary.js:14`)
  - This week "may rise/drop in price tonight" at ≥80 (`week.js:122,131`)
  - Planner at ≥80 (`planner.js:127,138`)

  The player sheet gets it right: it only says "Likely tonight" at 100% or more (`player-sheet.js:20`).
- **Fix:** use ≥100 for "tonight" wording. Label 75–99 as "rising (not tonight)", or use `priceRecord()` to show the actual hit rate.

### N5. Medium: Review's "projected before the deadline" is a re-run with today's model, not the saved projection. Confirmed. Affects the user's GW8.
- **Where:** `build.py:847,887,916` uses `project(ctx, g, …, {"use_flags": False})` with today's bootstrap, model and hindsight data. `review.js:96,99,103` labels the result "Projected before the deadline". The Decision score, its grade and "luck" (`build.py:899-907`) use the same re-run.
- **Evidence (user's GW8):**
  - Re-run XI total: **50.4**. The saved pre-deadline snapshot (`history/proj_gw8.json`): **46.8**.
  - Calvert-Lewin (346) re-runs at **4.0** but was shown as **2.01** before the deadline, when he was flagged 50% with a foot injury.
  - "Luck" therefore reads +1.6 instead of about +5.2.
- **Fix:** use `proj_gw{g}.json` where it exists (GW8 onwards), and label older weeks "re-run with the current model".

### N6. Medium/Low: priors take the last two seasons a player has in the PL, however old they are. Confirmed.
- **Where:** `make_priors.py:30` uses `history_past[-2:]` and weights them 2:1 whatever the gap.
- **How old:**
  - 42 of 481 priors come from before 2025/26.
  - 13 players with 200+ minutes this season use them. Most are from the promoted clubs:
    - Hull: Ajayi 2020/21, Egan, Giles and McBurnie 2023/24
    - Coventry: Grimes 2015/16
    - Ipswich: 6 players on 2024/25
    - Elsewhere: Tzolis (ARS) 2021/22 and Maitland-Niles (EVE) 2022/23
- **Pre-xG seasons:** FPL's `expected_goals` is 0.00 for seasons before 2022/23. So those priors pull xG/xA towards 0:
  - Ajayi (279): xg90 0.031 vs 0.053 without the prior. Over 6 GWs, xP is **15.6 vs 17.4**.
  - Tzolis (557): 12.2 vs 12.7.
- **UI:**
  - The player sheet tile shows "2020/21 pts 51" (Ajayi) and "2015/16 pts 3" (Grimes) as last season.
  - `model.js:26` says priors are "blended with 2025/26 and the two seasons before it". The code uses two seasons in total, not three.
- **Clean:** players with no prior (188 of 669) fall back to the positional average. Nothing is made up for them.
- **Fix:**
  - Keep only seasons from the last 2 calendar years.
  - Drop the xG/xA priors for seasons before 2022/23. Keep the minutes and points priors.
  - Correct the wording in `model.js:26`.

### N7. Low: two clean-sheet formulas in the UI. Confirmed.
- **Where:** the player sheet "Defence" line (`player-sheet.js:62`) and fixture swings (`fixtures.js:71`) use `exp(-xga)`. The model (`cs_k` 0.9) and the Fixtures grid (`fixtures.js:11`) use `exp(-0.9·xga)`.
- **Example:** Raya, GW9 at Liverpool (xGA 1.53). His player sheet says **22%**, but the Fixtures grid and xP use **25%**.
- **Fix:** use `csChance()` everywhere.

### N8. Low: "sell before the fall" alert for Calafiori, whose selling price wouldn't change. Confirmed. User's squad.
- **Evidence:** Calafiori is projected at −104% (a fall from £6.0m to £5.9m). His purchase price is £5.5m. Selling price now: 5.5 + ⌊(6.0−5.5)/2⌋ = **£5.7m**. After the fall: 5.5 + ⌊0.4/2⌋ = **£5.7m**.
- **The problem:** `stats.js:178` ("If you're selling him anyway, sell before then") and `moves-summary.js:14` ("sell first") would warn about a loss that doesn't happen.
- **Fix:** only show sell-before-fall alerts when `selling_price(now−1) < sell`.

### N9. Low (suspected): home advantage is set at about half of what this season shows, and team goals are slightly over-projected.
- **Setting:** `fplmodel.py:24` (`home: 1.05`) means a home/away goal ratio of 1.10. The same value is hard-coded again at `fixtures.js:66`.
- **This season:** 80 matches, with home goals 1.51 a game against away 1.26, a ratio of **1.20**. The bookmakers' implied goals (`odds.json`) give **1.19**.
- **Out of sample:** I re-projected GW3–8 one week ahead (120 team-matches):
  - Goals for a team: **projected 1.47, actual 1.33** (+10%).
  - Clean sheets: projected 28.2%, actual 30.0%.
- **Why it matters:** this fits the first audit's pattern (attackers over-projected, goalkeepers under). Since no upcoming odds exist (C7), nothing corrects it for GW9.
- **Promoted-club ratings** come from data, not hard-coding: COV att 0.78 / def 1.16, HUL 0.76 / 1.19, IPS 0.87 / 1.24.
- **Fix:** re-tune `home` and the league goal level with `bench.py` against 2025/26 plus 2026/27, and take `H` from `D.meta` in `fixtures.js`.

### N10. Low: GW1–2 output of players who changed club is credited to their new club. Confirmed.
- **Where:** `prepare()` (`fplmodel.py:205-210`) adds each player's xG to his **current** `team`. The minutes window and `opp_of` also use the current team.
- **Evidence:**
  - Ndiaye (237, now MCI): 0.24 + 0.02 xG of Everton's and Bournemouth's matches went to MCI.
  - Muñoz (201, now NFO): 0.23 of Everton's went to NFO.
  - Enzo (155), Grealish (238) and Iroegbunam (240) played for their old clubs in GW1–2.
- **Effect:** total about 0.5 xG. That is a small effect on team ratings and on the "trend" tables.
- **Fix:** take the team from the fixture (`explain[].fixture`) in `prepare()`.

### N11. Low: hard-coded claims that are never recomputed.
- `model.js:23`: "In testing on GW3–7 this lifted the correlation … from 0.40 to 0.42". This is a fixed number, and today's measured correlation is 0.429.
- `model.js:12`: "a correlation around 0.4 is about as good as public models get" has no source.
- `explain.js:27`: live rank is "Usually within 10–20% of the real figure". Nothing in the repo measures this.
- **Fix:** compute these from `accuracy`, or soften them to "in our testing" with a date.

### N12. Low: penalty takers.
- **Source:** `penalties_order` comes from FPL, which is real data.
- **Double counting:** FPL `expected_goals` already includes penalties (Groß: 2.16 FPL xG against 1.17 non-penalty plus 0.76 penalty xG on Understat). So the +0.05 xG/90 boost for the #1 taker (`fplmodel.py:492`) counts penalties twice. The effect is small.
- **Injured #1 takers:** Saka (12) and Szoboszlai (368) are injured #1s, so their clubs' stand-ins get no boost.
- **Who actually took them:** at Sunderland, Le Fée (#2) took both penalties (Diarra is #1). At Ipswich, Flemming (#2) took one.
- **Fix:** use non-penalty xG plus `p_pen × pen_xg`, and give the boost to the #2 taker when the #1 is out.

---

## User's squad (8122679 BACK2BACK; matches the API)

| Player | Finding |
|---|---|
| João Pedro (165) | **N1** (GW10–14 about 2.4× too low), **N2** (says "no injury news" under a 0% injury flag) |
| Calafiori (8) | **N3** ("started about 39%" after starting 7 of 8; suspected double penalty), **N8** (misleading sell-before-fall alert) |
| Raya (1) | **N7** (clean-sheet chance shows 22% on his sheet, 25% elsewhere) |
| Calvert-Lewin (346) | **N5** (GW8 review re-run says 4.0, but 2.01 was shown before the deadline) |
| Gibbs-White (480) | First-audit fix holds: p_start 1.00, xP 4.02, now in the XI |
| Others | No new issues |

---

## Checked and clean
- **Free transfers = 4.** Walking through the history (first set of chips, wildcard and free hit keep your FTs, cap of 5) gives 1, 2, 3, 4, 5, 5, then 4 after 2 transfers, then 4 after 1. Bank £0.8m and value £101.8m match the GW8 picks.
- **Selling prices:** all 15 match FPL's half-profit rule rounded down. Purchase prices skip free-hit transfers and use the latest buy, for example Haaland bought at 15.5, now 15.8, sells for 15.6.
- **Captain and vice:** Haaland is captain and Groß vice in the squad. The lineup captain is Haaland and vice Palmer, from the model.
- **Chips:**
  - Used: Bench Boost GW2, Free Hit GW3, Wildcard GW4.
  - First-half Triple Captain is available until GW19.
  - Second set runs GW20–38, all available, matching `bootstrap.chips`.
  - Triple Captain text: "+xP from the chip" and "TC xP × 3" are both correct.
- **Hits and free-transfer roll-over in the browser:** `ftTable` (`plan.js`) and `plan-solver.js` both use a cap of 5, a −4 hit and a banked FT valued at 1.5. `bankAt` uses selling prices for the original 15.
- **Plans:** none of the 15 plans takes a hit.
- **Player odds:** not used in xP (README says so, and grep confirms nothing reads them). Built 28 Oct for GW9, 5 names unmatched. Shown only on Health.
- **Price data:** comes from FPL's own projection field and is labelled "FPL projection". The update time (01:30 UK) matches `price_change_deadlines`.
- **Ownership samples:** the sample size is shown on Rivals and Health (2,000 top 10k, 499 near you, GW8, built 23 Oct, about 50 minutes after the deadline). Effective ownership counts a Triple Captain as 2, as the code says. The template backfill for GW1–7 is labelled as survivor-biased in the UI.
- **Players with 0 minutes:** none has xP above 0.3, so new signings get no made-up projections.
- **Priors:** players with no prior fall back to the positional average.
- **Blank and double gameweeks:** none in GW9–14. The code scales the appearance term by the number of fixtures.
- **Bonus:** comes from each player's own BPS and bonus rate. Saves come from the goalkeeper's rate scaled by opponent xG. Cards are yellow-card rate only (no reds, own goals or missed penalties, so slightly optimistic but nothing invented).
- **Hard-coded percentages in `model.js`** (70% xG, 70% market, 85% direct odds, 5-GW minutes window) match `DEFAULTS`.

## Couldn't check
- **Live `data.json` on GitHub Pages and football-data.co.uk:** proxy 403. I used a rebuild from the same commit instead.
- **GitHub Actions run history:** no API access.
- **The Odds API:** no key.
- **Browser rendering at phone and desktop widths:** not done. I reviewed the code paths only.
- **Whether FPL's "Expected back" for `d`-flagged players precedes their absences in earlier GWs:** the status log for GW1–7 is backfilled from news history, so N1 could also hit older GWs. I only quantified GW8.
- **N9 tuning:** I didn't run `bench.py` or `backtest.py`. They need the 2025/26 archive and a model change, which is out of scope for a read-only audit.

Scratch files: `/tmp/claude-0/-home-claude/fc363e4d-54d2-50a5-86e1-b07d0ede8d0b/scratchpad/a2/` (scripts), `/tmp/claude-0/-home-claude/fc363e4d-54d2-50a5-86e1-b07d0ede8d0b/scratchpad/api2/` (API snapshots), `/tmp/claude-0/-home-claude/fc363e4d-54d2-50a5-86e1-b07d0ede8d0b/scratchpad/run2/` (build).

---

## Status check, 12 Nov 2026 (FL-138)

Read-only check of N1, N2, N3, N8 and N11 against `main` at `230d9be`. Nothing was changed. N4, N6 and N7 are covered by other backlog items, and the rest weren't in scope.

| Finding | Status | Where it is handled now |
|---|---|---|
| **N1.** Post-deadline injury read as "lost his place" | **Fixed** | `fplmodel.py`: `late_news_absences()` (news posted from a day before deadline *k* to two days after GW *k*'s last kick-off, for a regular who didn't start) and `doubtful_absences()` (a `d` flag of 75% or less saved at the deadline). `prepare()` adds both to `out`, behind `DEFAULTS["late_abs"] = True`. This is the fix this audit proposed. |
| **N2.** "No injury news" under an injury flag | **Fixed** | `player-sheet.js:58-59`: the "may have lost his place" sentence only shows when `status === "a"` and there is no news; otherwise it says "He missed his club's last game (FPL news since: …)". |
| **N3.** "Started about 39% of recent games" | **Fixed** | `player-sheet.js`: the tile is now "Chance to start next game", next to a real "Starts, last N" tile (`st5`, from `build.py`). The sentence prints the real count ("He started N of his club's last M games") and calls the model figure "a …% chance to start next game, weighting the latest games most". |
| **N8.** Sell-before-fall false alarm | **Fixed** | `plan.js:118` `fallCostsYou()` applies FPL's half-profit rule. Every fall alert checks it: Stats prices (`stats.js:192`), the moves summary (`moves-summary.js:10`), Home risks (`week.js:69`) and the Planner (`planner.js:138`). The watchlist only colours the %. |
| **N11.** Hard-coded claims never recomputed | **Not fixed** | Still verbatim: `model.js:23` "lifted the correlation … from 0.40 to 0.42" (GW3–7), `model.js:12` "a correlation around 0.4 is about as good as public models get", and `explain.js:28` live rank "Usually within 10-20% of the real figure". Logged as **FL-154**. |

Notes:
- N1 was checked by reading the code and following it into `prepare()`. I found no unit test that pins it (no test mentions `late_news_absences` or `doubtful_absences`). I also found no `docs/model-log.md` entry under those names. Git history in this clone is shallow (108 commits), so the PR that added it couldn't be traced from here.
- N3's "suspected double penalty" for players flagged after a sub appearance is part of the N1 mechanism above.
