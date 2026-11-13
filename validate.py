#!/usr/bin/env python3
"""Check a freshly built data.json before it is published.

Usage: python3 validate.py [site/data.json]

Hard failures (exit 1, so the Refresh workflow stops before uploading and the last good site stays live):
  - a player FPL lists at 0% for next gameweek with more than 0.5 xP that week
  - an Understat id used for two FPL players, or an FPL id claimed by two Understat ids (incl. overrides)
  - next gameweek's xP breakdown (xp_detail) not adding up to xP within 0.05
  - NaN, infinite or negative xP
  - a probability outside 0-1 (p_start, psub, dc_rate, chance of 10+/6+/blank, chance of playing)
  - a real-starts record (st5) with more starts than games
  - expected minutes (xmin) outside 0-180, or NaN
  - the xMins minutes model switched on but any player with a next-GW fixture fell back to the old counts
  - a per-GW points series (s_pts) whose length isn't the current gameweek, or a DefCon record with odd points,
    fewer than 2 points per hit, or fewer minutes than its 60+ minute games need; more starts than minutes
  - a Review week whose pre-deadline snapshot (history/proj_gw{g}.json) exists but wasn't used
  - free transfers outside 0-5, a negative/non-finite bank, or squad prices that break FPL's half-profit rule
  - a Free Hit restore that disagrees with independent FPL chip history and the pre-Free-Hit picks
  - an empty squad after the first deadline
  - an Odds API upcoming-odds row (FL-092) with result probabilities outside 0-1 or not summing to 1, an over-2.5
    chance outside 0-1, or expected goals outside 0.05-6
  - meta.odds rows used + rows dropped not adding up to odds/odds.json's rows (data.json built from another odds file)
  - a player kept as close to a return (FL-093) whose status, chance, minutes or news don't match the reason given
  - priors.json holding a prior from a season outside its "seasons" list (the two calendar seasons before this one)
  - model settings exported for the site (meta.model) that aren't finite numbers in a sane range: home 1.0-1.5,
    cs_k 0.5-1.5 (data built before the field existed has no meta.model and is not checked)
  - xmins_sell switched on and its next-GW numbers (data-extra.json "xmins_sell") out of range (see below)
Warnings (printed, and saved in data.json "health" for the Health page; never fail the build):
  - before a deadline: history/deadline_gw{g}.json missing, stale, for other weeks or without your players
  - legacy data without squad_source evidence outside a required Free Hit restore
  - inside 6 hours of a deadline: more than 45 minutes since the previous refresh (meta.prev_built), or no record
    of the previous refresh at all. Late data here means stale injury flags, prices and pre-deadline snapshots
  - a player with 300+ minutes and no Understat row (and no manual override)
  - Understat shots data missing, or covering fewer matches than have finished while its last successful update
    is over 36 hours old (understat.py keeps the previous file when Understat is down, so it goes stale silently)
  - no betting odds for any of next gameweek's fixtures
  - next GW's rows in odds/upcoming.json's latest snapshot that odds/odds.json doesn't use (postponed since?)
  - the latest Odds API upcoming-odds fetch failing (odds/upcoming.json last_error), or the last finished-deadline
    gameweek's history/fixture_odds_gw*.json missing a 72, 24 or 3 h snapshot
  - odds/odds.json holding extra rows (a stale upcoming row or a fixture id twice); the model uses one per fixture
  - this season's played-match odds failed to download or came back short (played rows carried over from the last
    good odds file, or none to carry)
  - once the current gameweek is finished, per-GW points not adding up to a player's FPL total (DD hauls column)
  - no season starts for any player (Points leaders Starts column)
  - last-6 goals or assists above the season figure
  - a gameweek in progress with no pre-deadline snapshot for the xP table's live column (meta.xp_cur), or a
    snapshot with fewer entries than half the players (it normally leaves out only players projected 0)
  - player odds (history/player_odds_gw*.json) for the latest finished-deadline gameweek missing a checkpoint
    (72, 24 or 3 h before the deadline), when that gameweek's file uses per-checkpoint snapshots. The model doesn't
    use player odds yet; this keeps the history complete for testing them. Skipped (not warned) when no file has
    snapshots, e.g. with no ODDS_API_KEY.
  - Understat chances created looking wrong in understat/fpl_players.json meta: more than 10 matched players with
    3+ key passes but none created (kp_no_cc), any player left uncredited because he shares a club and name with
    another (cc_ambiguous), or a team title with no short code (cc_no_code). A file without these fields (built
    before they existed) is not checked.
  - an input that didn't load or is past its schedule: last-season priors (missing, or over 15 days old), match odds
    (missing, or over 48 hours old) and the ownership sample (missing, or for an earlier gameweek); see check_sources
  - selling-informed xMins (shadow while xmins_sell is off): skipped, players with a next-GW fixture it didn't
    cover, players with no selling data (NaN inputs), failed element-summary fetches, and any start chance outside
    0-1 / xMin outside 0-180 / bad xP (an error instead once xmins_sell is on)
"""
import datetime as dt
import json, math, os, sys
from collections import Counter
from odds_players import snapshots

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


PRIORS_STALE_DAYS, ODDS_STALE_H = 15, 48


def _age_hours(newer, older):
    """Hours between two ISO timestamps, or None when either can't be read."""
    try:
        return (dt.datetime.fromisoformat(newer.replace("Z", "+00:00"))
                - dt.datetime.fromisoformat(older.replace("Z", "+00:00"))).total_seconds() / 3600
    except (AttributeError, TypeError, ValueError):
        return None


def check_logs(D, warnings):
    """history/news.json, history/prices.json (FL-120) and crowd/history.json (FL-152): build.py never overwrites one it couldn't read, so its history
    survives, but until someone fixes the file the injury news history and the price-change track record stop growing
    and this build shows them from nothing. A warning (Data health), not an error: everything else is right.
    Missing / late / ambiguous: a build.py older than FL-120 has no "ok" key; it is not checked (it would already have
    overwritten the file). A file that doesn't exist yet (first run) is not an error: build.py starts it, ok True.
    """
    src = D.get("sources") or {}
    for key, path, what in (("news", "history/news.json", "injury news history"),
                            ("prices", "history/prices.json", "price-change track record"),
                            ("template", "crowd/history.json", "template tracker history")):
        if (src.get(key) or {}).get("ok") is False:
            warnings.append(f"{path} is unreadable and was left untouched: the {what} isn't being updated "
                            f"until the file is fixed or restored from Git history")


def check_rival_subs(D, errors):
    """FL-153: each auto-sub on a mini-league row takes a starter (picks 1-11) off for a bench player (picks 12-15) of
    the same manager, and no player comes on twice. Data from before FL-153 has no live_subs and is not checked."""
    for lg in ((D.get("crowd") or {}).get("leagues") or []):
        for r in lg.get("rows") or []:
            subs, p = r.get("live_subs"), r.get("picks")
            if not subs or not p:
                continue
            xi, bench = {el for el, _ in p[:11]}, {el for el, _ in p[11:]}
            ins = [s[1] for s in subs]
            if any(s[0] not in xi or s[1] not in bench for s in subs) or len(set(ins)) != len(ins):
                errors.append(f"Mini-league {lg.get('name')}: {r.get('player')}'s live auto-subs {subs} don't match "
                              f"his picks (starter off, bench player on, each once)")


def check_arrivals(D, errors):
    """FL-030: the arrival guess (new to the PL) only for a player with no prior in priors.json, as a weight in (0, 1],
    with his start chance marked assumed for the site."""
    pri = set(((load(os.path.join(HERE, "priors.json")) or {}).get("players") or {}))
    for pl in D.get("players", []):
        a_ = pl.get("arrival")
        if a_ is None:
            continue
        if is_bad(a_) or not 0 < a_ <= 1 or pl.get("start_assumed") is not True or str(pl.get("id")) in pri:
            errors.append(f"{pl.get('name')} ({pl.get('id')}): arrival guess {a_} needs a weight in (0, 1], "
                          f"start_assumed and no prior in priors.json")


def check_school(D, warnings):
    """FL-147: the FPL School relay address (fpl_school.json) must be an https:// address; anything else is ignored by
    the build (the tab then says the relay isn't set up), so say why on Health. No school block (older data): skipped."""
    sc = D.get("school")
    if sc and sc.get("relay_raw") and not sc.get("relay"):
        warnings.append(f"fpl_school.json relay {sc['relay_raw']!r} isn't an https:// address, so the FPL School tab "
                        f"can't use it (docs/fpl-school-relay.md)")


def check_club_then(meta, warnings):
    """FL-065: a player who has changed clubs has each past week credited to the club he played for then
    (fplmodel.clubs_then). A week that can't be told (one game at a club he has since left) is credited to no club: warn
    with the players and gameweeks. Data from before FL-065 has no meta.club_ambiguous and is not checked."""
    amb = meta.get("club_ambiguous")
    if amb:
        warnings.append(f"Club at the time unclear for {len(amb)} player-week(s) with xG ({', '.join(f'player {p} GW{g}' for p, g in amb[:5])}"
                        f"{'…' if len(amb) > 5 else ''}): that xG counts for no team and his opponent adjustment is off")


def check_model_inputs(meta, errors, warnings):
    """The status log and europe.json (FL-072): build.py runs on without either, so these are the only sign.

    Status log (history/status.json, every flagged player's status at each deadline): without it the model can't tell
    an injured player from a dropped one and its minutes go wrong. An ERROR once a deadline has passed (cur_gw >= 1)
    when the file is missing or unreadable: the publish stops, and because the Refresh workflow commits nothing when
    validate.py fails, the next refresh errors again until the log is restored (build.py would otherwise start a new,
    near-empty log and the loss would go quiet). Before the first deadline a missing log is normal. A log that loads but
    holds no deadline once the season has started is a warning: it can't be told apart from a log that was reset.
    europe.json (midweek European fixtures): missing or unreadable is a warning (the rotation allowance and the "also
    plays" flags are missing; an entry that fails part way leaves the competitions after it without them), and so is
    each competition skipped because its dates or teams aren't confirmed.
    Missing / late / ambiguous: data from a build.py older than FL-072 has neither key and is not checked.
    """
    cur = meta.get("cur_gw") or 0
    sl = meta.get("status_log")
    if sl:
        if sl.get("state") in ("missing", "unreadable") and cur >= 1:
            errors.append(f"Status log (history/status.json) {sl['state']}"
                          f"{': ' + sl['error'] if sl.get('error') else ''}. The model can't tell injured from dropped "
                          f"players without it: restore the file from Git history")
        elif sl.get("state") == "ok" and cur >= 1 and not sl.get("gws"):
            warnings.append("Status log (history/status.json) has no deadline saved although the season has started: "
                            "the model has no injury history")
    eu = meta.get("europe")
    if eu:
        if eu.get("state") == "missing":
            warnings.append("europe.json is missing: no rotation allowance or 'also plays' flags for European midweeks")
        elif eu.get("state") == "unreadable":
            warnings.append(f"europe.json didn't load ({eu.get('error')}): some or all European midweeks have no rotation "
                            f"allowance or 'also plays' flag")
        if eu.get("unconfirmed"):
            warnings.append(f"europe.json: {', '.join(eu['unconfirmed'])} skipped (dates or teams not confirmed), so no "
                            f"rotation allowance for those matches until \"confirmed\" is set")


def check_sources(D, warnings):
    """Warn when an input the model or the plans lean on didn't load, or is older than its own schedule allows.

    build.py carries on when priors.json, odds/odds.json or crowd/latest.json can't be read, so without these the only
    sign is a quieter page. All warnings (Health page), not errors: each fallback still gives usable projections,
    and stopping the publish would freeze prices and injury flags too.
      - last-season priors: not loaded (player rates fall back to this season plus the positional average), or
        priors.json older than 15 days (the workflow runs every Monday);
      - match odds: not loaded (team ratings come from xG and results only, no market blend), or older than
        48 hours (odds.py leaves the file untouched when football-data.co.uk can't be reached);
      - ownership sample: not loaded (Play safe and Chase rank can't be planned), or for an earlier gameweek than
        the current one (those strategies, EO and the live rank then rest on last week's teams).
    Missing / late / ambiguous: a section whose key isn't in data.json at all (an older build) is not checked; a
    timestamp that can't be read is reported as unknown age, never treated as fresh.
    """
    meta = D["meta"]
    if "priors_season" in meta:
        if not meta["priors_season"]:
            warnings.append("Last-season priors didn't load (priors.json): player rates use this season and the "
                            "positional average only")
        else:
            pr = load(os.path.join(HERE, "priors.json")) or {}
            age = _age_hours(meta.get("built"), pr.get("built"))
            if age is None:
                warnings.append("Last-season priors: age unknown (no readable 'built' time in priors.json)")
            elif age > PRIORS_STALE_DAYS * 24:
                warnings.append(f"Last-season priors are {age / 24:.0f} days old (the weekly Update last-season priors "
                                f"job may be failing): new signings and returning players may have none")
    if "odds" in meta:
        od = meta["odds"]
        if not od:
            warnings.append("Match odds didn't load (odds/odds.json): team ratings come from xG and results only, "
                            "with no betting-market blend")
        else:
            age = _age_hours(meta.get("built"), od.get("built"))
            if age is None:
                warnings.append("Match odds: age unknown (no readable 'built' time in odds/odds.json)")
            elif age > ODDS_STALE_H:
                warnings.append(f"Match odds are {age / 24:.1f} days old (football-data.co.uk not reached since "
                                f"{od.get('built')}): recent results are missing from the betting-market ratings")
    if "crowd" in D:
        cr, cur = D["crowd"], meta.get("cur_gw")
        if not cr:
            if cur:   # before GW1 there is nothing to sample yet
                warnings.append("Ownership sample didn't load (crowd/latest.json): no Play safe or Chase rank plans, "
                                "EO or live rank")
        elif cur and cr.get("gw") != cur:
            warnings.append(f"Ownership sample is for GW{cr.get('gw')}, not the current GW{cur}: Play safe, Chase rank, "
                            f"EO and live rank use last week's teams until crowd.py samples this week's")
        if cr and cr.get("complete") is False:   # FL-082 (None: a sample from before the field existed)
            warnings.append(f"Ownership sample incomplete: {cr.get('failed')} FPL requests failed, so the top-10k, rank-band "
                            f"and mini-league samples are smaller than planned; crowd.py retries on its next run")
        if cr:   # FL-141: FPL's own all-manager figures, shown next to the top 10k on Rivals
            tp, oc = cr.get("total_players"), cr.get("overall_chips")
            if tp is not None and not (isinstance(tp, int) and tp > 0):
                errors.append(f"crowd.total_players should be a positive whole number, got {tp!r}")
            for k, v in (oc or {}).items():
                if not (isinstance(v, (int, float)) and 0 <= v <= 100):
                    errors.append(f"crowd.overall_chips[{k}] should be a % from 0 to 100, got {v!r}")
        if cr and cr.get("rank_assumed"):
            warnings.append("Ownership sample: FPL gave no overall rank, so 'managers near your rank' is centred on an "
                            "assumed 100,000")


def is_bad(x):
    return x is None or type(x) not in (int, float) or math.isnan(x) or math.isinf(x)


def check_model_meta(D, errors):
    """meta.model: the model settings the site reads instead of hard-coding (home advantage, clean-sheet constant).
    Missing meta.model (a data.json built before the field existed): not checked, the site falls back to the values
    the model used then (core/model.js modelSet). Present but wrong type, missing key or out of range: error."""
    m = D.get("meta", {}).get("model")
    if m is None:
        return
    if not isinstance(m, dict):
        errors.append(f"meta.model is not an object: {m!r}")
        return
    for key, lo, hi in (("home", 1.0, 1.5), ("cs_k", 0.5, 1.5)):
        v = m.get(key)
        if is_bad(v) or not lo <= v <= hi:
            errors.append(f"meta.model.{key} = {v!r}: expected a finite number in {lo}-{hi} (the site's clean-sheet % "
                          f"and far-fixture estimates use it)")


US_STALE_H = 36


def check_understat(meta, warnings):
    """Warn when the Understat file (shots, big chances, shot maps, set-piece xG on Stats) is missing or behind.

    understat.py exits cleanly and keeps the previous file when Understat can't be reached, so the only sign is an
    old "built" stamp. Behind = fewer matches than have finished AND the last successful update over 36 hours ago;
    a few hours behind on a matchday is normal and stays quiet. A warning only: the model doesn't use this data
    (sp_match is off), so stale shots must not stop the publish.
    Missing / late / ambiguous: data from an older build.py (no finished_fixtures key) is not checked; no Understat
    meta at all warns as missing; a "built" stamp that can't be read counts as stale, never as fresh.
    """
    fin = meta.get("finished_fixtures")
    if fin is None:
        return
    us = meta.get("understat") or {}
    n = us.get("matches")
    if not us or type(n) is not int:
        warnings.append("No Understat data: Stats shots, set-piece threat and shot maps have nothing to show")
        return
    if n >= fin:
        return
    try:
        age = (dt.datetime.fromisoformat(meta["built"].replace("Z", "+00:00"))
               - dt.datetime.fromisoformat(us["built"].replace("Z", "+00:00"))).total_seconds() / 3600
    except (AttributeError, KeyError, TypeError, ValueError):
        age = None
    if age is None or age > US_STALE_H:
        when = f"last updated {age / 24:.0f} days ago" if age is not None else "last update time unknown"
        warnings.append(f"Understat is behind: {n} of {fin} finished matches, {when} ({us.get('built')}). "
                        f"Stats shots, set-piece threat and shot maps are missing the recent games")


KP_NO_CC_MAX = 10


def check_created(us_meta, warnings):
    """Understat chances created (cc) come from shot rows keyed by club and assister name; key passes (kp) come
    from Understat's own player totals. They should broadly agree, so many players with key passes and no chance
    created means the name/club lookup has broken again (audit B9). Warnings only: the Understat columns are
    display stats. Missing input: a meta without a field (file built before the field existed, or no file at
    all) is not checked for it, and nothing is assumed."""
    n = us_meta.get("kp_no_cc")
    if n is not None and n > KP_NO_CC_MAX:
        warnings.append(f"Understat: {n} matched players have 3+ key passes but no chances created "
                        f"(more than {KP_NO_CC_MAX}; check the club/name lookup in understat.py)")
    if us_meta.get("cc_ambiguous"):
        warnings.append(f"Understat: {us_meta['cc_ambiguous']} matched players share a club and name with another "
                        "Understat player, so their chances created are left at 0 (see the understat.py output)")
    if us_meta.get("cc_no_code"):
        warnings.append(f"Understat: {us_meta['cc_no_code']} team titles have no short code, so their players' "
                        "chances created are not counted")


def check_squad(D, detail, errors, warnings):
    """Check money in integer £0.1m units and restore against independent FPL history/picks.

    Old builds without source evidence warn in normal weeks; a required Free Hit restore without evidence errors.
    Missing or stale source data cannot certify a restore. Before GW1 an empty squad is allowed.
    """
    meta, manager = D["meta"], D.get("manager", {})
    ft, bank = manager.get("free_transfers"), manager.get("bank")
    if type(ft) is not int or not 0 <= ft <= 5:
        errors.append(f"free_transfers = {ft}: must be an integer between 0 and 5")
    if is_bad(bank) or bank < 0:
        errors.append(f"bank = {bank}: must be finite and non-negative")
    sq = D.get("squad", [])
    ids = [s["id"] for s in sq]
    if (ids or meta.get("picks_gw")) and (len(ids) != 15 or len(set(ids)) != 15):
        errors.append(f"squad has {len(ids)} picks ({len(set(ids))} different): plans need 15 different players")
    players = {p["id"]: p for p in D["players"]}
    for row in sq:
        pid = row["id"]
        values = [row.get("buy"), row.get("sell"), players.get(pid, {}).get("price")]
        if any(is_bad(v) or v < 0 or abs(v * 10 - round(v * 10)) > 1e-8 for v in values):
            errors.append(f"Squad player {pid}: buy/sell/current prices {values} must be finite, non-negative £0.1m amounts")
            continue
        buy, sell, current = (round(v * 10) for v in values)
        expected = current if current <= buy else buy + (current - buy) // 2
        if sell > current:
            errors.append(f"Squad player {pid}: selling price {sell / 10:g} exceeds current price {current / 10:g}")
        if sell != expected:
            errors.append(f"Squad player {pid}: selling price {sell / 10:g}, FPL profit rule expects {expected / 10:g}")

    src = detail.get("squad_source")
    pg, ng = meta.get("picks_gw"), meta.get("next_gw")
    history_fh = any(h.get("gw") == pg and h.get("chip") == "freehit" for h in D.get("history", []))
    if not src:
        if meta.get("fh_restored") or (history_fh and ng is not None and pg and ng > pg):
            errors.append("Free Hit restore has no independent FPL history/picks evidence")
        else:
            warnings.append("No squad_source evidence: Free Hit history cannot be independently checked (rebuild data)")
        return
    if (detail.get("built") != meta.get("built") or src.get("team_id") != meta.get("team_id")
            or src.get("picks_gw") != pg or not isinstance(src.get("chips"), list)):
        errors.append("Free Hit source evidence is stale, incomplete or belongs to another entry/gameweek")
        return
    actual_fh = any(c.get("name") == "freehit" and c.get("event") == pg for c in src["chips"])
    restore = bool(actual_fh and ng is not None and pg and ng > pg)
    if bool(meta.get("fh_restored")) != restore:
        errors.append("Free Hit restore flag disagrees with FPL chip history")
    expected_gw = pg - 1 if restore else pg
    if meta.get("squad_gw") != expected_gw:
        errors.append(f"Squad source GW{meta.get('squad_gw')}, FPL history requires GW{expected_gw}")
    if restore:
        before = src.get("before_free_hit") or {}
        previous = before.get("ids", [])
        if (before.get("gw") != expected_gw or len(previous) != 15 or len(set(previous)) != 15):
            errors.append("Free Hit restore has no complete pre-Free-Hit picks for the required gameweek")
        elif set(ids) != set(previous):
            errors.append(f"Free Hit restore squad differs from FPL GW{expected_gw} picks: "
                          f"missing {sorted(set(previous) - set(ids))}, unexpected {sorted(set(ids) - set(previous))}")


GAP_WINDOW_H, GAP_MAX_MIN = 6, 45   # FL-111: every 30 minutes in the 6 h before a deadline, plus 15 minutes' slack


def check_refresh_gap(meta, warnings):
    """Warn when refreshes are far apart close to a deadline.

    The Refresh workflow is scheduled every 30 minutes in the 6 hours before a deadline (scripts/refresh_due.py;
    hourly otherwise, every 10 minutes during matches), but GitHub starts scheduled runs late or not at all (gaps of
    8 hours seen in November 2026), so the last data before a deadline can be hours old. A warning, never an error: a
    late refresh is still the freshest data there is, and stopping the publish would make it worse.
    Missing / late / ambiguous: data built by an older build.py has no prev_built key and is not checked; a key that
    is None or unreadable inside the window gets its own warning (the gap is unknown, not assumed fine); no deadline,
    or a deadline that has passed or is more than 6 hours away, is not checked.
    """
    if "prev_built" not in meta or not meta.get("deadline") or not meta.get("built"):
        return
    try:
        built = dt.datetime.fromisoformat(meta["built"].replace("Z", "+00:00"))
        deadline = dt.datetime.fromisoformat(meta["deadline"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return
    left = deadline - built
    if not dt.timedelta(0) < left <= dt.timedelta(hours=GAP_WINDOW_H):
        return
    hours = left.total_seconds() / 3600
    try:
        gap = (built - dt.datetime.fromisoformat(meta["prev_built"].replace("Z", "+00:00"))).total_seconds() / 60
    except (AttributeError, TypeError, ValueError):
        warnings.append(f"Refresh gap unknown {hours:.1f} h before the GW{meta.get('next_gw')} deadline: no record of "
                        f"the previous refresh (history/status.json)")
        return
    if gap > GAP_MAX_MIN:
        warnings.append(f"Refresh gap: {gap / 60:.1f} h since the previous refresh, {hours:.1f} h before the "
                        f"GW{meta.get('next_gw')} deadline (scheduled every 30 minutes this close to a deadline). GitHub's schedule is "
                        f"unreliable: set up the backup scheduler in the README")


def check_picks_sections(D, warnings):
    """Review and You vs the model rest on your picks for each finished gameweek, fetched one week at a time (FL-070).

    Warnings (Data health), not errors: the rest of the site is right, and stopping the publish would freeze live scores.
      - a week listed in review.skipped / vs_model.skipped (picks or live scores not fetched this update);
      - Review empty although FPL has your points for a finished gameweek;
      - You vs the model empty or missing although a finished gameweek you played has a forecast saved before its
        deadline (history/proj_gwN.json), which is all it needs.
    Missing / late / ambiguous: data from a build.py older than FL-070 has no review.skipped and is only checked for
    being empty; no finished gameweek yet (pre-season, GW1 in play) is not checked.
    """
    fin = set(D["meta"].get("finished_gws") or [])
    played = {h.get("gw") for h in D.get("history") or []} & fin
    rv, vm = D.get("review") or {}, D.get("vs_model") or {}
    for name, sec in (("Review", rv), ("You vs the model", vm)):
        if sec.get("skipped"):
            warnings.append(f"{name}: GW{', GW'.join(map(str, sec['skipped']))} left out, picks or scores not fetched "
                            f"this update (the next refresh tries again)")
    if played and not rv.get("weeks"):
        warnings.append(f"Review is empty although {len(played)} finished gameweek(s) have your points: picks not fetched?")
    saved = {g for g in played if os.path.exists(os.path.join(HERE, "history", f"proj_gw{g}.json"))}
    if saved and not vm.get("weeks"):
        warnings.append(f"You vs the model is empty although GW{', GW'.join(map(str, sorted(saved)))} have a forecast "
                        f"saved before the deadline")


def check_setpieces(D, errors, warnings):
    """Set-piece change log (setpiece_log.py, history/setpieces.json, FL-069).

    A warning (Data health) when the log couldn't be used this build: no file and no deployed list to seed it from
    (the next build tries again), or a file that is unreadable (left untouched for someone to fix). Not an error: the
    takers table is still right, only the change list is missing. An error for a change row the Stats page would print
    wrongly (unknown type, a team we don't list, or a date that isn't YYYY-MM-DD); a warning if they're out of order.
    Missing / late / ambiguous: data from a build.py older than FL-069 has no status and is not checked for it.
    """
    sp = D.get("setpieces")
    if not sp:
        return
    st = sp.get("status")
    if st == "seed_failed":
        warnings.append("Set-piece history: history/setpieces.json is missing and the deployed site couldn't be read "
                        "to seed it, so no change list this build (the next build tries again)")
    elif st == "unreadable":
        warnings.append("Set-piece history: history/setpieces.json is unreadable and was left untouched; the Stats page "
                        "shows the last deployed list, if any. Fix or restore the file from Git history")
    teams = {str(k) for k in (D.get("teams") or {})} if isinstance(D.get("teams"), dict) else None
    ch = sp.get("changes") or []
    for c in ch:
        bad_date = not (isinstance(c.get("date"), str) and len(c["date"]) == 10 and c["date"][4] == "-" == c["date"][7])
        if c.get("type") not in ("pen", "cor", "fk") or bad_date or (teams is not None and str(c.get("team")) not in teams):
            errors.append(f"Set-piece change {c}: unknown type, team or date")
    if any(a.get("date", "") < b.get("date", "") for a, b in zip(ch, ch[1:])):
        warnings.append("Set-piece history is out of order (newest change should come first)")


def check_season_end(meta, errors, warnings):
    """FL-060: after GW38's deadline FPL lists no next gameweek, and build.py publishes a season-end build (no forecasts
    or plans, season stats and live scores only) with meta.season_over set.

    An error when FPL drops the next gameweek before the last one is current (an API fault mid-season): publishing would
    blank the Planner and every xP, so the publish stops and the last good site stays up. Also an error when the flag
    disagrees with next_gw, or a season-end build still carries forecast weeks. A correct season-end build gets one
    warning so Data health says why there are no forecasts.
    Missing / late / ambiguous: data from a build.py older than FL-060 has no season_over key and is not checked (it
    can't say whether the season was over). season_over set but no last_gw is an error: the end of the season can't be
    confirmed, so the publish stops rather than assume it.
    """
    if "season_over" not in meta:
        return
    over, nxt, cur, last = meta["season_over"], meta.get("next_gw"), meta.get("cur_gw"), meta.get("last_gw")
    if bool(over) != (nxt is None):
        errors.append(f"Season end: season_over is {over} but next_gw is {nxt}")
        return
    if not over:
        return
    if last is None or cur != last:
        errors.append(f"FPL lists no next gameweek but the current one is GW{cur}, not the last (GW{last}): "
                      f"not publishing a site with no forecasts mid-season")
        return
    if meta.get("proj_gws") or meta.get("plan_gws"):
        errors.append(f"Season over but forecast weeks {meta.get('proj_gws')} / plan weeks {meta.get('plan_gws')} are set")
        return
    warnings.append(f"Season over: GW{cur} was the last gameweek, so there are no forecasts or plans until FPL opens next season")


def check_recommended(D, errors, warnings):
    """FL-108: the recommended plan is worked out once in build.py (optimise.recommended) and every screen uses it.
    Errors: data.json has plans but no "recommended"; a recommended key that isn't a plan of that strategy; a choice the
    rule (fewest moves within plan_rules.recommend_margin of the strategy's best vs_roll) wouldn't make, worked out again
    here on its own. Warnings: a strategy that has move options but no recommendation; the target You vs the model
    shows for the week to come isn't the Balanced recommendation (possible only in a build after the deadline)."""
    plans = D.get("plans") or {}
    if not plans:
        return
    rec = D.get("recommended")
    if not isinstance(rec, dict):
        errors.append("Plans published without 'recommended': Home, the Planner and the journal can't agree on a plan")
        return
    margin = (D.get("plan_rules") or {}).get("recommend_margin")
    if margin is None:
        errors.append("plan_rules.recommend_margin missing: the recommended plan can't be checked")
        return
    for mode in ("balanced", "safe", "chase"):
        keys = [k if mode == "balanced" else f"{mode}_{k}" for k in ("roll", "one", "two", "three")]
        keys = [k for k in keys if k in plans and plans[k].get("vs_roll") is not None]
        want = None
        if keys:
            top = max(plans[k]["vs_roll"] for k in keys)
            want = next(k for k in keys if plans[k]["vs_roll"] >= top - margin - 1e-9)
        got = rec.get(mode)
        if got is not None and got not in plans:
            errors.append(f"Recommended {mode} plan {got!r} isn't among the plans")
        elif got != want:
            errors.append(f"Recommended {mode} plan is {got!r} but the rule picks {want!r}")
        elif keys and got is None:
            warnings.append(f"No recommended {mode} plan although it has move options")
    nxt = ((D.get("vs_model") or {}).get("next") or {}).get("target") or {}
    if nxt.get("plan") and rec.get("balanced") and nxt["plan"] != rec["balanced"]:
        # the snapshot is rewritten by every build before the deadline, so the two differ only in a build that ran
        # after it (the snapshot then keeps the last pre-deadline plan): a warning, not an error
        warnings.append(f"You vs the model's next target is plan {nxt['plan']} but Home recommends {rec['balanced']} "
                        "(the saved pre-deadline plan differs from this build's)")
def check_club_limit(D, errors, warnings):
    """FL-074: FPL's limit of 3 from one club. A real move between Premier League clubs can leave the squad holding more;
    FPL lets you keep them but takes no transfer until you're back to 3 from that club. Every plan week is replayed from
    the squad: a week with a transfer must end with at most 3 from every club, a week without one may hold no more than
    you hold now. Error if a plan breaks that; warning (Health page) while your squad holds more than 3 from a club."""
    team = {p["id"]: p.get("team") for p in D["players"]}
    squad = [s["id"] for s in D.get("squad") or []]
    if not squad or any(team.get(i) is None for i in squad):
        return   # check_squad reports a squad with players missing from the list
    def counts(ids):
        c = {}
        for i in ids:
            c[team.get(i)] = c.get(team.get(i), 0) + 1
        return c
    held = counts(squad)
    for t, c in held.items():
        if c > 3:
            name = ((D.get("teams") or {}).get(str(t)) or {}).get("name", f"club {t}")
            warnings.append(f"Your squad has {c} players from {name}: FPL takes no transfer until you're back to 3, "
                            "so the plans sell one in any week they make a move")
    for k, pl in (D.get("plans") or {}).items():
        sq = set(squad)
        for wk in pl.get("weeks", []):
            sq = (sq - set(wk.get("out", []))) | set(wk.get("in", []))
            for t, c in counts(sq).items():
                limit = 3 if wk.get("in") else max(3, held.get(t, 0))
                if c > limit:
                    errors.append(f"Plan {k} GW{wk.get('gw')}: {c} players from club {t}"
                                  + (" in a week with transfers" if wk.get("in") else ""))
                    break


def main(path):
    with open(path) as f:
        D = json.load(f)
    detail = load(os.path.join(os.path.dirname(os.path.abspath(path)), "data-extra.json")) or {}
    extra = detail.get("players", {})
    us = (load(os.path.join(HERE, "understat", "fpl_players.json")) or {}).get("players", {})
    ov = {int(k): int(v) for k, v in (load(os.path.join(HERE, "understat_overrides.json")) or {}).items() if not k.startswith("_")}
    g = D["meta"].get("next_gw")
    gk = str(g)
    errors, warnings = [], []
    name = lambda p: f'{p["name"]} ({p["id"]})'

    for p in D["players"]:
        xp = p.get("xp") or {}
        for gw, v in xp.items():
            if is_bad(v) or v < 0:
                errors.append(f"{name(p)}: xP GW{gw} = {v}")
        nxt = xp.get(gk, 0) or 0
        if p.get("chance") == 0 and not is_bad(nxt) and nxt > 0.5:
            errors.append(f"{name(p)}: {nxt:.2f} xP in GW{g} but FPL has him at 0% ({p.get('news') or p.get('status')})")
        probs = {"p_start": p.get("p_start"), "psub": p.get("psub"), "dc_rate": p.get("dc_rate")}
        if p.get("chance") is not None:
            probs["chance"] = p["chance"] / 100
        for gw, d in (p.get("dist") or {}).items():
            for i, lab in enumerate(("p10", "p6", "blank")):
                probs[f"dist GW{gw} {lab}"] = d[i]
        for k, v in probs.items():
            if v is not None and (is_bad(v) or not 0 <= v <= 1):
                errors.append(f"{name(p)}: {k} = {v} (not a probability)")
        det = (extra.get(str(p["id"])) or {}).get("xp_detail", p.get("xp_detail"))
        if det is not None and xp.get(gk) is not None and (any(is_bad(v) for v in det.values())
                or is_bad(xp[gk]) or abs(sum(det.values()) - xp[gk]) > 0.05):
            errors.append(f"{name(p)}: xp_detail {det} is non-finite or does not add up to xP GW{g} = {xp[gk]}")
        xm = p.get("xmin")
        if xm is not None and (is_bad(xm) or not 0 <= xm <= 180):
            errors.append(f"{name(p)}: xmin = {xm} (expected minutes must be 0-180)")
        st5 = p.get("st5")
        if st5 is not None and not (len(st5) == 2 and 0 <= st5[0] <= st5[1]):
            errors.append(f"{name(p)}: st5 = {st5} (starts must be between 0 and games)")
        mins = p.get("mins") or 0
        if mins >= 300 and str(p["id"]) not in us and p["id"] not in ov.values():
            warnings.append(f"{name(p)}: {mins} minutes but no Understat match (add to understat_overrides.json)")

    # Stats tabs (Goals & assists, Defence, Points leaders) read these from data-extra.json
    cur = D["meta"].get("cur_gw") or 0
    off_total = []
    for p in D["players"]:
        # Starts lives in data.json: a missing optional detail row must not disable this check.
        stt = p.get("starts")
        if stt is not None and (is_bad(stt) or stt < 0 or stt > (p.get("mins") or 0) or stt > 2 * cur):
            errors.append(f"{name(p)}: {stt} starts with {p.get('mins')} minutes by GW{cur} (impossible)")
        ex = extra.get(str(p["id"]))
        if ex is None:
            continue
        sp = ex.get("s_pts")
        if sp is not None and len(sp) != cur:
            errors.append(f"{name(p)}: s_pts has {len(sp)} gameweeks, current GW is {cur}")
        elif sp is not None and sum(sp) != p.get("pts"):
            off_total.append(name(p))
        d = ex.get("dcs")
        if d and ("pts" in d) and (d["pts"] % 2 or d["pts"] < 2 * d["hits"] or d.get("mins", 0) < 60 * d["apps"]):
            errors.append(f"{name(p)}: DefCon record {d} is impossible (points odd, below 2 per hit, or too few minutes)")
        ga = ex.get("ga6")
        if ga and (ga["g"] > (p.get("goals") or 0) or ga["a"] > (p.get("assists") or 0) or min(ga.values()) < 0):
            warnings.append(f"{name(p)}: last-6 goals/assists {ga['g']}/{ga['a']} above season {p.get('goals')}/{p.get('assists')}")
    check_squad(D, detail, errors, warnings)
    check_refresh_gap(D["meta"], warnings)
    # pre-deadline snapshot (deadline_snapshot.py): written every build until the deadline, so a missing or stale one now
    # means this gameweek's record would be lost. A warning (Health page), not an error: it must not stop the publish.
    dl = D["meta"].get("deadline")
    if g and dl and dl > (D["meta"].get("built") or ""):
        sp_ = load(os.path.join(HERE, "history", f"deadline_gw{g}.json"))
        if sp_ is None:
            warnings.append(f"No pre-deadline snapshot for GW{g} (history/deadline_gw{g}.json): its 5-GW xP, minutes, odds and plans won't be kept")
        else:
            if sp_.get("gw") != g or sp_.get("plan_gws") != D["meta"].get("plan_gws"):
                warnings.append(f"Pre-deadline snapshot for GW{g} is for GW{sp_.get('gw')} / weeks {sp_.get('plan_gws')}, not this build's {D['meta'].get('plan_gws')}")
            gone = [s_["id"] for s_ in D.get("squad", []) if str(s_["id"]) not in sp_.get("xp", {})]
            if gone:
                warnings.append(f"Pre-deadline snapshot for GW{g} is missing {len(gone)} of your players")
            try:
                lag = (dt.datetime.fromisoformat(D["meta"]["built"]) - dt.datetime.fromisoformat(sp_["built"])).total_seconds()
            except (KeyError, TypeError, ValueError):
                lag = None
            if lag is None or lag > 15 * 60:
                warnings.append(f"Pre-deadline snapshot for GW{g} wasn't rewritten this build (saved {sp_.get('built')})")
            # start chance as the forecast used it: never above FPL's flag or his chance before flags, and only missing
            # for a blank. Missing: a player not in data.json (no flag or chance to test against) is skipped.
            row_ = {p_["id"]: p_ for p_ in D["players"]}
            wrong, none_ = [], []
            for k_, m_ in sp_.get("mins", {}).items():
                p_ = row_.get(int(k_))
                if p_ is None:
                    continue
                s_ = m_[0]
                if s_ is None:
                    if (sp_.get("xp", {}).get(k_) or [0])[0] > 0:
                        none_.append(k_)
                elif not 0 <= s_ <= 1 or s_ > (p_.get("p_start") or 0) + 0.011 or (p_.get("chance") is not None and s_ > p_["chance"] / 100 + 0.011):
                    wrong.append(p_["name"])
            if wrong:
                warnings.append(f"Pre-deadline snapshot for GW{g}: start chance above the flag or the model's own for {', '.join(wrong[:5])}")
            if none_:
                warnings.append(f"Pre-deadline snapshot for GW{g}: no start chance for {len(none_)} players with xP (first ids {', '.join(none_[:5])})")
    # you vs the model (F1): impossible teams or results are errors; your score not matching FPL's is a warning (it
    # would mean the scoring rules missed something, so the head-to-head can't be trusted that week)
    vm = D.get("vs_model")
    if vm:
        pos_ = {p["id"]: p["pos"] for p in D["players"]}
        for w in vm.get("weeks", []):
            sq_ = set(int(i) for i in w.get("xp", {}))
            for side in ("you", "model"):
                t_ = w[side]
                # Older cached builds predate this field; when supplied it must match the scorer's chip rule.
                if t_.get("captain_multiplier", 3 if w.get("chip") == "3xc" else 2) != (3 if w.get("chip") == "3xc" else 2):
                    errors.append(f"You vs the model GW{w['gw']}: {side} captain multiplier disagrees with the chip")
                if len(t_["xi"]) != 11 or len(set(t_["xi"]) | set(t_["bench"])) != 15 or not set(t_["xi"]) <= sq_:
                    errors.append(f"You vs the model GW{w['gw']}: the {side} side isn't 11 + 4 from the same 15")
            n_ = {k: sum(pos_.get(i) == k for i in w["model"]["xi"]) for k in ("GKP", "DEF", "MID", "FWD")}
            if n_["GKP"] != 1 or n_["DEF"] < 3 or n_["MID"] < 2 or n_["FWD"] < 1:
                errors.append(f"You vs the model GW{w['gw']}: the model's XI isn't a legal formation ({n_})")
            # FL-109, actual v actual: the week is your actual points after hits against what the model's team actually
            # scored after its hits. "suggested": the recommended plan (FL-108) scored with its bench and auto-subs; its
            # points must add up from the per-player actuals shown on the pitch. "your 15" (assumed): the model's pick
            # from your 15, scored the same way (w["model"]["pts"]). exp (projected) must still match the plan.
            tg_ = w.get("target") or {}
            cap_mult_ = 3 if tg_.get("basis") == "your 15" and w.get("chip") == "3xc" else 2
            if tg_.get("captain_multiplier", cap_mult_) != cap_mult_:
                errors.append(f"You vs the model GW{w['gw']}: target captain multiplier disagrees with its basis")
            ok_ = tg_.get("par") is not None and tg_.get("actual") == tg_["par"]
            if tg_.get("basis") == "your 15":
                xp_ = {int(k): v for k, v in w.get("xp", {}).items()}
                m_ = w["model"]
                cnt_ = m_["xi"] + (m_["bench"] if w.get("chip") == "bboost" else [])
                exp_ = sum(xp_.get(i, 0) for i in cnt_) + (2 if w.get("chip") == "3xc" else 1) * xp_.get(m_["cap"], 0)
                ok_ = (ok_ and tg_.get("assumed") is True and abs(tg_["exp"] - exp_) <= 0.2
                       and tg_.get("pts") == m_["pts"] == tg_["actual"])
            elif tg_.get("basis") == "suggested":
                xi_, bench_, src_ = tg_.get("xi", []), tg_.get("bench") or [], tg_.get("bench_src")
                ok_ = (ok_ and len(xi_) == 11 and abs(tg_["exp"] - (tg_["xp"] - 4 * tg_["hits"])) <= 0.2
                       and tg_.get("actual") == (tg_.get("pts") or 0) - 4 * tg_["hits"]
                       and src_ in ("saved", "derived", "missing")
                       and (src_ == "missing" or (len(bench_) == 4 and len(set(xi_) | set(bench_)) == 15)))
                if ok_:   # its points add up from what each player scored, after its auto-subs
                    fin_ = list(xi_)
                    for o_, i_ in tg_.get("subs") or []:
                        fin_ = [i_ if x == o_ else x for x in fin_]
                    pts_ = {int(k): v for k, v in (tg_.get("xi_pts") or {}).items()}
                    sum_ = sum(pts_.get(i, 0) for i in fin_) + (tg_["captain_multiplier"] - 1) * (
                        pts_.get(tg_.get("armband"), 0) if tg_.get("armband") is not None else 0)
                    if sum_ != tg_.get("pts"):
                        errors.append(f"You vs the model GW{w['gw']}: the model's team scores {sum_} from its players, not {tg_.get('pts')}")
                if src_ in ("derived", "missing"):
                    warnings.append(f"You vs the model GW{w['gw']}: the suggested team's bench was "
                                    + ("rebuilt (not saved with the plan)" if src_ == "derived" else "not available, so no auto-subs for it"))
            else:
                ok_ = False
            if not ok_:
                errors.append(f"You vs the model GW{w['gw']}: target {tg_.get('basis')} {tg_.get('actual')}/{tg_.get('par')} doesn't add up")
            elif w["you_net"] != w["you"]["pts"] - w["hits"]:
                errors.append(f"You vs the model GW{w['gw']}: your score after hits {w['you_net']} isn't {w['you']['pts']} - {w['hits']}")
            else:
                want = "W" if w["you_net"] > tg_["par"] else "L" if w["you_net"] < tg_["par"] else "D"
                if w["res"] != want:
                    errors.append(f"You vs the model GW{w['gw']}: result {w['res']} but {w['you_net']} v target {tg_['par']}")
            if tg_.get("assumed"):
                warnings.append(f"You vs the model GW{w['gw']}: no saved suggestion, target assumed from the model's best pick from your 15")
            if w["you"]["pts"] != w["fpl_pts"]:
                warnings.append(f"You vs the model GW{w['gw']}: your team scores {w['you']['pts']} by our rules but {w['fpl_pts']} on FPL")
        for t_ in [w["target"] for w in vm.get("weeks", [])] + [(vm.get("next") or {}).get("target") or {}]:
            if any(pos_.get(o) != pos_.get(i) for o, i in zip(t_.get("out", []), t_.get("in", []))):
                errors.append(f"You vs the model: the model's moves {t_.get('out')} -> {t_.get('in')} aren't paired by position")
        nt_ = (vm.get("next") or {}).get("target")
        if nt_ and nt_.get("captain_multiplier", 2) != 2:
            errors.append("You vs the model: next week's suggested target must use captain ×2")
        # FL-109: the week to come hasn't been played, so it has no score to beat (par None); exp is its projection
        if nt_ and nt_.get("par") is not None:
            errors.append(f"You vs the model: GW{vm['next'].get('gw')} hasn't been played but has a score to beat ({nt_['par']})")
        if nt_ and (len(nt_.get("xi", [])) != 11 or is_bad(nt_.get("exp")) or len(nt_.get("out", [])) != len(nt_.get("in", []))):
            errors.append(f"You vs the model: next week's target doesn't add up ({nt_.get('exp')}, {len(nt_.get('xi', []))} in the XI)")
        for w in vm.get("weeks", []):
            t_ = w.get("target") or {}
            if t_.get("basis") == "suggested" and set(map(int, t_.get("xi_xp", {}))) != set(t_.get("xi", [])) | set(t_.get("bench") or []):
                errors.append(f"You vs the model GW{w['gw']}: projected points missing for part of the suggested XI")
        if len(vm.get("trail", [])) != len(vm.get("weeks", [])) or (vm.get("trail") and vm["trail"][-1]["run"] != vm.get("run")):
            errors.append("You vs the model: the streak trail doesn't match the weeks or the current run")
        rec = vm.get("record", {})
        if sum(rec.values()) != len(vm.get("weeks", [])):
            errors.append(f"You vs the model: record {rec} doesn't add up to {len(vm['weeks'])} weeks")
        if vm.get("held", 0) > 2 or vm.get("run", 0) > vm.get("best", 0):
            errors.append(f"You vs the model: impossible streak (run {vm.get('run')}, best {vm.get('best')}, wildcards {vm.get('held')})")
        if vm.get("skipped"):
            warnings.append(f"You vs the model: GW{', GW'.join(map(str, vm['skipped']))} skipped (picks or live data missing)")
    if all(p.get("starts") is None for p in D["players"]):
        warnings.append("No season starts from FPL this build: Points leaders shows '–' for Starts")
    if not extra:
        warnings.append("data-extra.json missing or empty: Stats and player detail show 'no data'")
    elif len(extra) < len(D["players"]):
        warnings.append(f"data-extra.json has {len(extra)} players for {len(D['players'])} listed: Stats tabs show 'no data' for the rest")
    # mid-gameweek the per-GW series counts finished matches only, so it trails FPL's total; once the gameweek is
    # finished they must agree, or DD hauls can miss a gameweek FPL counted
    if off_total and D["meta"].get("cur_finished"):
        warnings.append(f"{len(off_total)} players' GW points don't add up to their FPL total (DD hauls, player charts) "
                        f"(e.g. {', '.join(off_total[:3])})")

    # minutes model: if xMins is on, every player with a next-GW fixture must have been projected by it
    mm = D["meta"].get("minutes_model")
    if mm and mm.get("xmins_on") and mm.get("counts"):
        errors.append(f"xMins minutes model is on but {mm['counts']} players with a GW{g} fixture fell back to the "
                      f"old counts ({mm.get('xmins', 0)} used xMins)")

    # selling-informed xMins (selling.py): coverage and ranges; warnings while it is a shadow, errors once it is live
    if mm and "sell" in mm:
        si, live_ = mm["sell"], mm.get("xmins_sell_on")
        bad_ = errors if live_ else warnings
        tag = "xmins_sell" + ("" if live_ else " (shadow)")
        if si.get("error"):
            bad_.append(f"{tag}: not computed ({si['error']})")
        else:
            if si.get("failed"):
                warnings.append(f"{tag}: {si['failed']} element-summary fetches failed; their selling inputs are NaN")
            fxp = mm.get("fixture_players")
            if fxp is not None and si.get("n") is not None and si["n"] < fxp:
                warnings.append(f"{tag}: covers {si['n']} of {fxp} players with a GW{g} fixture (the rest keep the plain model)")
            if si.get("sell_nan"):
                warnings.append(f"{tag}: {si['sell_nan']} of {si.get('n')} players have no selling data for GW{g} "
                                f"(model ran with missing inputs)")
            sh = (load(os.path.join(os.path.dirname(os.path.abspath(path)), "data-extra.json")) or {}).get("xmins_sell")
            if not live_ and si.get("n") and not sh:
                warnings.append(f"{tag}: counted {si['n']} players but data-extra.json has no xmins_sell block")
            for pid, row in ((sh or {}).get("players") or {}).items():
                ps_l, ps_s, xm_l, xm_s, xp_l, xp_s, ss = row
                if any(is_bad(v) or not 0 <= v <= 1 for v in (ps_l, ps_s)):
                    bad_.append(f"{tag}: player {pid} start chance {ps_l} / {ps_s} (not a probability)")
                if is_bad(xm_s) or not 0 <= xm_s <= 180:
                    bad_.append(f"{tag}: player {pid} xMin {xm_s} (must be 0-180)")
                if is_bad(xp_s) or xp_s < 0:
                    bad_.append(f"{tag}: player {pid} xP {xp_s}")
                if ss is not None and (is_bad(ss) or not -1 <= ss <= 1):
                    bad_.append(f"{tag}: player {pid} sell_share {ss} (must be -1 to 1)")

    # Understat: one-to-one both ways
    dup_us = [u for u, n in Counter(v["us_id"] for v in us.values()).items() if n > 1]
    if dup_us:
        errors.append(f"Understat ids used for more than one FPL player: {dup_us}")
    dup_fpl = [f for f, n in Counter(ov.values()).items() if n > 1]
    by_us = {v["us_id"]: int(k) for k, v in us.items()}
    dup_fpl += [f for u, f in ov.items() if u in by_us and by_us[u] != f]
    dup_fpl += [int(k) for k, v in us.items() if int(k) in ov.values() and ov.get(v["us_id"]) != int(k)]
    if dup_fpl:
        errors.append(f"FPL ids with more than one Understat source (check understat_overrides.json): {sorted(set(dup_fpl))}")
    check_created((load(os.path.join(HERE, "understat", "fpl_players.json")) or {}).get("meta") or {}, warnings)

    check_understat(D["meta"], warnings)
    # decision journal (D5a): every move is accounted for once, every player mentioned has a row, and the model's plan is
    # the same one the You vs the model target used for that week
    jr = D.get("journal")
    if jr:
        tg_plan = {w["gw"]: w["target"].get("plan") for w in (D.get("vs_model") or {}).get("weeks", [])}
        for e in jr.get("weeks", []):
            key = lambda xs: sorted(map(tuple, xs))
            mm = (e.get("model") or {}).get("moves", [])
            if key(e["both"] + e["yours"]) != key(e["you"]["moves"]) or key(e["both"] + e["skipped"]) != key(mm):
                errors.append(f"Journal GW{e['gw']}: moves don't add up (both + yours / both + skipped)")
            need = {i for mv in e["you"]["moves"] + mm for i in mv} | {e["you"]["captain"], (e.get("model") or {}).get("captain")}
            miss = sorted(i for i in need if i is not None and str(i) not in e["players"])
            if miss:
                errors.append(f"Journal GW{e['gw']}: no pre-deadline row for players {miss}")
            pos_j = {p["id"]: p["pos"] for p in D["players"]}
            if any(pos_j.get(o) != pos_j.get(i) for o, i in mm + e["you"]["moves"]):
                errors.append(f"Journal GW{e['gw']}: a move swaps players in different positions")
            if e.get("model") and e["gw"] in tg_plan and tg_plan[e["gw"]] and tg_plan[e["gw"]] != e["model"]["plan"]:
                errors.append(f"Journal GW{e['gw']}: model plan {e['model']['plan']} isn't the You vs the model target's {tg_plan[e['gw']]}")
        fin_ = set(D["meta"].get("finished_gws") or [])
        for e in jr.get("weeks", []):
            oc = e.get("outcome")
            if not oc:
                continue
            if any(g < e["gw"] or g >= e["gw"] + oc["of"] for g in oc["gws"]) or ("finished_gws" in D["meta"] and not set(oc["gws"]) <= fin_):
                errors.append(f"Journal GW{e['gw']}: results use gameweeks {oc['gws']} outside its window or not finished")
            for k, m in oc["moves"].items():
                if m["gain"] != m["in_pts"] - m["out_pts"]:
                    errors.append(f"Journal GW{e['gw']}: {k} gain {m['gain']} isn't {m['in_pts']} - {m['out_pts']}")
        if jr.get("skipped"):
            warnings.append(f"Journal: picks not fetched for GW{', GW'.join(map(str, jr['skipped']))}, so no entry")

    # Review: "projected before the deadline" must be the saved snapshot wherever one exists, and a week without one
    # shows nothing projected at all (F1f: "no saved forecast", never a re-run with today's model)
    for w in (D.get("review") or {}).get("weeks", []):
        if not os.path.exists(os.path.join(HERE, "history", f'proj_gw{w["gw"]}.json')):
            if w.get("proj_src") != "none" or w.get("xi_proj") is not None or w.get("decision") or w.get("model_cap") \
                    or any(t[5] is not None for t in w.get("team", [])):
                errors.append(f'Review GW{w["gw"]}: no forecast was saved before this deadline but the review shows a projection')
        if os.path.exists(os.path.join(HERE, "history", f'proj_gw{w["gw"]}.json')):
            if is_bad(w.get("xi_proj")) or w.get("proj_src") != "snapshot" or (w.get("decision") and w["decision"].get("src") != "snapshot"):
                errors.append(f'Review GW{w["gw"]}: a pre-deadline snapshot exists but was not used for a finite Review projection')

    check_model_meta(D, errors)

    # xP table live column: the gameweek in progress should have its pre-deadline projections
    xc = D["meta"].get("xp_cur")
    if xc and xc.get("status") != "snapshot":
        warnings.append(f'xP table GW{xc.get("gw")} live column has no projections ({xc.get("status")})')
    elif xc and xc.get("in_snapshot", 0) < 0.5 * len(D["players"]):
        warnings.append(f'xP table GW{xc["gw"]} live column: the snapshot has only {xc.get("in_snapshot", 0)} players '
                        f'for {len(D["players"])} listed; players not in it show 0')

    # odds for next gameweek
    odds = load(os.path.join(HERE, "odds", "odds.json")) or {}
    # played-match odds (odds.carry_played): the results file failed or came back short, so played rows were carried
    # over from the last good file. The ratings still work; the warning is so a lasting failure gets noticed. An odds
    # file written before this status existed has none and is not checked.
    ost = odds.get("status") or {}
    if ost and (not ost.get("past_ok") or ost.get("kept_played")):
        n_played = sum(1 for m in odds.get("matches", []) if m.get("played"))
        warnings.append(f"Match odds: this season's results file {'did not load' if not ost.get('past_ok') else 'came back short'} "
                        f"(since {ost.get('past_failed_since')}); {ost.get('kept_played', 0)} of {n_played} played matches "
                        f"carried over from the last good file" + ("" if n_played >= 20 else
                        ": fewer than 20, so the betting-market team ratings are off"))
    # one row per fixture (FL-112): fplmodel.prepare already uses one row per fixture whatever the file holds, so the
    # model can't double-count; extra rows in the file only mean odds.py hasn't rewritten it yet (e.g. football-data
    # down), so warn rather than stop the publish
    dup = sorted(f for f, n in Counter(m.get("fixture") for m in odds.get("matches", []) if m.get("fixture") is not None).items() if n > 1)
    extra = ((D["meta"].get("odds") or {}).get("file_extra_rows") or 0)
    if dup or extra:
        warnings.append(f"Match odds: odds/odds.json has {extra} extra row(s) ({len(dup)} fixture id(s) more than once"
                        + (f", e.g. {', '.join(map(str, dup[:5]))}" if dup else "") + "); the model used one row per "
                        "fixture, and odds.py rewrites the file on its next successful run")
    used = (D["meta"].get("odds") or {}).get("matches")
    if odds.get("matches") and used is not None and used + extra != len(odds["matches"]):
        errors.append(f"Match odds: the build used {used} rows and dropped {extra}, but odds/odds.json has "
                      f"{len(odds['matches'])}: data.json was built from a different odds file")
    # upcoming match odds from The Odds API (FL-092, odds.fetch_upcoming)
    for m in odds.get("matches", []):
        if m.get("src") != "odds_api":
            continue
        ps = [m.get("p_h"), m.get("p_d"), m.get("p_a")]
        if any(is_bad(x) or not 0 < x < 1 for x in ps) or abs(sum(ps) - 1) > 0.01:
            errors.append(f"Match odds fixture {m.get('fixture')}: Odds API result probabilities {ps} don't make a 0-1 set summing to 1")
        if m.get("p_over") is not None and (is_bad(m["p_over"]) or not 0 < m["p_over"] < 1):
            errors.append(f"Match odds fixture {m.get('fixture')}: Odds API over-2.5 chance {m['p_over']} outside 0-1")
        if any(is_bad(m.get(k)) or not 0.05 <= m[k] <= 6 for k in ("lam_h", "lam_a")):
            errors.append(f"Match odds fixture {m.get('fixture')}: Odds API expected goals {m.get('lam_h')}-{m.get('lam_a')} outside 0.05-6")
    up = load(os.path.join(HERE, "odds", "upcoming.json")) or {}
    latest = up.get("latest") or {}
    # snapshot used: the latest snapshot's next-GW rows must be in odds.json (odds.py merged them)
    if g and latest.get("rows"):
        have = {m.get("fixture") for m in odds.get("matches", []) if m.get("src") == "odds_api"}
        lost = [r["fixture"] for r in latest["rows"] if r.get("gw") == g and r["fixture"] not in have
                and not any(m.get("fixture") == r["fixture"] and m.get("played") for m in odds.get("matches", []))]
        if lost:   # a warning, not an error: a fixture postponed since the snapshot is rightly left out
            warnings.append(f"Match odds: the Odds API snapshot of {latest.get('built')} has GW{g} odds for fixture(s) "
                          f"{', '.join(map(str, lost[:5]))} that odds/odds.json doesn't use")
    err = up.get("last_error") or {}
    if err.get("at") and (not latest.get("built") or err["at"] > latest["built"]):
        warnings.append(f"Upcoming match odds (The Odds API) failed at {err['at']}: {str(err.get('message'))[:160]}; "
                        f"using the snapshot of {latest.get('built') or 'none'}")
    fo = sorted(((int(f[len("fixture_odds_gw"):-5]), f) for f in os.listdir(os.path.join(HERE, "history"))
                 if f.startswith("fixture_odds_gw") and f.endswith(".json")), reverse=True)
    for fg, f in fo:
        if g and fg >= g:
            continue   # still being collected
        missing = [h for h in ("72", "24", "3") if h not in (load(os.path.join(HERE, "history", f)) or {}).get("snapshots", {})]
        if missing:
            warnings.append(f"Upcoming match odds GW{fg}: no {', '.join(m + ' h' for m in missing)} snapshot "
                            f"(check the ODDS_API_KEY secret and credits)")
        break
    if g and not any(m.get("gw") == g and not m.get("played") for m in odds.get("matches", [])):
        warnings.append(f"No betting odds for any GW{g} fixture: fixture xG comes from team ratings only")

    # player odds history: the last gameweek whose deadline has passed should have all three checkpoints
    po = sorted(((int(f[len("player_odds_gw"):-5]), f) for f in os.listdir(os.path.join(HERE, "history"))
                 if f.startswith("player_odds_gw") and f.endswith(".json")), reverse=True)
    for pg, f in po:
        if g and pg >= g:   # the coming gameweek is still being collected (season over: none is, check them all)
            continue
        data = load(os.path.join(HERE, "history", f)) or {}
        snaps = snapshots(data)
        for label, snap in snaps.items():
            for fixture in snap.get("fixtures", {}).values():
                for pid, row in fixture.get("players", {}).items():
                    for field in ("p_score", "p_assist_raw", "p_assist"):
                        if field in row and (is_bad(row[field]) or not 0 <= row[field] <= 1):
                            errors.append(f"Player odds GW{pg} {label} player {pid}: invalid {field}")
                    if "p_assist_raw" in row and "p_assist" in row and row.get("assist_pairs", 0) < 1:
                        errors.append(f"Player odds GW{pg} {label} player {pid}: fair assist chance without paired prices")
        if "snapshots" in data:
            missing = [h for h in ("72", "24", "3") if h not in snaps]
            if missing:
                warnings.append(f"Player odds GW{pg}: no {', '.join(m + ' h' for m in missing)} snapshot "
                                f"(check the ODDS_API_KEY secret and credits)")
        break
    # FL-093: a player kept because he is close to a return must still meet the reason given for him, using the same
    # fields the rule tests (status, chance, news), and his start chance must be marked assumed for the site
    for pl in D["players"]:
        why = pl.get("returning")
        if not why:
            continue
        ok = pl.get("status") != "u" and pl.get("start_assumed") is True and {
            "back": pl.get("status") == "a" and not pl.get("mins"),
            "chance": pl.get("status") != "a" and (pl.get("chance") or 0) > 0,
            "date": pl.get("status") != "a" and any(w in (pl.get("news") or "").lower() for w in ("expected back", "suspended until")),
        }.get(why, False)
        if not ok:
            errors.append(f"{pl.get('name')} ({pl.get('id')}): kept as returning '{why}' but status {pl.get('status')}, "
                          f"chance {pl.get('chance')}, minutes {pl.get('mins')}, news {pl.get('news')!r} don't support it")
    check_arrivals(D, errors)
    check_rival_subs(D, errors)
    # FL-082: make_priors.py writes start_rate; a prior without it uses fplmodel's minutes guess (inert while start_prior
    # is 0). Warn rather than fail: priors.json built before FL-082 has none until the Monday Priors run.
    _pp = ((load(os.path.join(HERE, "priors.json")) or {}).get("players") or {})
    _no_sr = sum(1 for v in _pp.values() if "start_rate" not in v)
    if _pp and _no_sr:
        warnings.append(f"priors.json: {_no_sr} of {len(_pp)} priors have no start_rate (built before FL-082, or a season "
                        f"with no starts); the model's start prior would guess it from minutes (start_prior is off)")
    # FL-113: priors only from the seasons make_priors.py lists in priors.json "seasons" (the two calendar seasons
    # before this one). A file written before that field existed is not checked.
    pri = load(os.path.join(HERE, "priors.json")) or {}
    if pri.get("seasons"):
        allowed = {f"{y}/{(y + 1) % 100:02d}" for y in pri["seasons"]}
        bad = sorted({v.get("season") for v in (pri.get("players") or {}).values()} - allowed, key=str)
        if bad:
            errors.append(f"priors.json holds priors from season(s) {', '.join(map(str, bad))}, outside "
                          f"{', '.join(sorted(allowed))}: rates from old seasons (and 0 xG before 2022/23) would be used")
    check_sources(D, warnings)
    check_logs(D, warnings)
    check_model_inputs(D["meta"], errors, warnings)
    check_club_then(D["meta"], warnings)
    check_school(D, warnings)
    check_season_end(D["meta"], errors, warnings)
    check_setpieces(D, errors, warnings)
    check_picks_sections(D, warnings)
    # Planner strategy tabs (views/planner.js): each tab shows one optimiser plan per strategy. Every plan must name
    # players we list and field a legal XI; a strategy with no plans (build.py drops Play safe and Chase rank when the
    # field ownership file is missing) is a warning, and the tab says so instead of showing the Balanced plan.
    pids = {p["id"] for p in D["players"]}
    plans = D.get("plans") or {}
    if not plans and not D["meta"].get("season_over"):   # season over: check_season_end explains the empty planner
        warnings.append("No optimiser plans: the Planner strategy tabs show a 'no plan' message")
    for k, pl in plans.items():
        for wk in pl.get("weeks", []):
            unknown = [i for i in wk.get("in", []) + wk.get("out", []) + wk.get("xi", []) if i not in pids]
            if unknown:
                errors.append(f"Plan {k} GW{wk.get('gw')}: players {unknown[:5]} are not in the player list")
            if len(wk.get("xi", [])) != 11 or wk.get("captain") not in wk.get("xi", []):
                errors.append(f"Plan {k} GW{wk.get('gw')}: XI has {len(wk.get('xi', []))} players or captain outside it")
            if len(wk.get("in", [])) != len(wk.get("out", [])):
                errors.append(f"Plan {k} GW{wk.get('gw')}: {len(wk.get('in', []))} in vs {len(wk.get('out', []))} out")
    check_recommended(D, errors, warnings)
    check_club_limit(D, errors, warnings)
    # strategy budgets (optimise.strategy_plans): Play safe never below Balanced, Chase rank at most chase_budget below,
    # and no plan with transfers short of the profit rule. A breach means the solver ignored its floor: stop the publish.
    rules = D.get("plan_rules") or {}
    if plans and not rules:
        warnings.append("plan_rules missing: the strategy budgets can't be checked")
    # FL-075: the browser planner (Re-plan, Transfer paths' Optimise) solves with these and refuses without them
    need_ = ("pool", "decay", "bench_w", "hit", "max_moves_week", "eo_weeks", "ft_value", "variance", "variance_other")
    if plans and rules:
        miss_ = [k for k in need_ if rules.get(k) is None]
        if miss_:
            errors.append(f"plan_rules lacks the planner settings {miss_}: Re-plan would refuse to run")
        elif (set(rules["pool"]) != {"GKP", "DEF", "MID", "FWD"} or any(not isinstance(v, int) or v < 1 for v in rules["pool"].values())
              or not 0 < rules["decay"] <= 1 or not 0 <= rules["bench_w"] <= 1 or rules["eo_weeks"] < 1
              or any(len(v) != 2 or is_bad(v[0]) or is_bad(v[1]) for v in list(rules["variance"].values()) + [rules["variance_other"]])):
            errors.append(f"plan_rules planner settings out of range: pool {rules['pool']}, decay {rules['decay']}, "
                          f"bench_w {rules['bench_w']}, eo_weeks {rules['eo_weeks']}")
    for k, pl in plans.items():
        if "vs_balanced" not in pl or "vs_none" not in pl:
            if rules:
                errors.append(f"Plan {k}: no vs_balanced / vs_none figures")
            continue
        # NaN comparisons are false: reject non-finite inputs before enforcing any numeric budget.
        amounts = {f: pl.get(f) for f in ("vs_balanced", "vs_none")}
        if any(wk.get("hits", 0) for wk in pl.get("weeks", [])) and rules.get("hit_gain") is not None:
            amounts["hit_gain"] = pl.get("hit_gain")
        if any(is_bad(v) for v in amounts.values()):
            errors.append(f"Plan {k}: non-finite or missing budget figures {amounts}")
            continue
        mode = k.split("_")[0] if "_" in k else "balanced"
        budget = {"balanced": 0.0, "safe": rules.get("safe_budget", 0.0), "chase": rules.get("chase_budget", 2.0)}[mode]
        if pl["vs_balanced"] < -(budget + rules.get("tie", 0.1) + 0.01):
            errors.append(f"Plan {k}: {pl['vs_balanced']:+.2f} vs Balanced, over its {budget:g}-point budget")
        nh = sum(wk.get("hits", 0) for wk in pl.get("weeks", []))
        cap = (rules.get("max_hits") or {}).get(mode)
        if cap is not None and any(wk.get("hits", 0) > cap for wk in pl.get("weeks", [])):
            errors.append(f"Plan {k}: takes more than {cap} hit(s) in a week ({mode} allows {cap})")
        if nh and rules.get("hit_gain") is not None and pl.get("hit_gain", -99) < rules["hit_gain"] * nh - 0.01:
            errors.append(f"Plan {k}: {nh} hit(s) gaining {pl.get('hit_gain', 'unknown')} vs no hits, short of the hit rule")
        moved = any(wk.get("in") for wk in pl.get("weeks", []))
        # FL-073: Roll isn't exempt; a Roll plan whose later moves miss the rule is replaced by the keep-squad plan
        if moved and pl["vs_none"] < rules.get("min_profit", 1.0) - 0.01:
            errors.append(f"Plan {k}: {pl['vs_none']:+.2f} vs no transfers, short of the profit rule")
        # FL-110: moves this week must beat rolling this week (the same strategy's Roll plan, vs_roll) by min_profit
        if pl.get("weeks") and pl["weeks"][0].get("in"):
            if pl.get("vs_roll") is None:
                errors.append(f"Plan {k}: makes moves this week but has no vs_roll, so the profit rule can't be checked")
            elif is_bad(pl["vs_roll"]) or pl["vs_roll"] < rules.get("min_profit", 1.0) - 0.01:
                errors.append(f"Plan {k}: {pl['vs_roll']} vs rolling this week, short of the profit rule")
    # FL-125: the Planner's "vs no transfers" is vs_none, rebuilt in the browser from xp_total and ft_left with
    # plan_rules.ft_value. Without ft_value it falls back to 1.5 and could disagree with data.json, so its absence
    # with plans published is an error. Every plan's value must be xp_total + ft_value * ft_left, and value - vs_none
    # the same keep-the-squad baseline for every plan (one figure, one baseline). Plans without these fields were
    # already reported above.
    ftv = rules.get("ft_value")
    if plans and rules and (is_bad(ftv) or ftv < 0):
        errors.append(f"plan_rules.ft_value is {ftv!r}: the Planner's 'vs no transfers' can't match the plans")
    elif plans and rules:
        bases = {}
        for k, pl in plans.items():
            if any(is_bad(pl.get(f)) for f in ("value", "xp_total", "ft_left", "vs_none")):
                continue
            if abs(pl["value"] - (pl["xp_total"] + ftv * pl["ft_left"])) > 0.02:
                errors.append(f"Plan {k}: value {pl['value']} isn't xP {pl['xp_total']} + {ftv:g} x {pl['ft_left']} FTs banked")
            bases[k] = pl["value"] - pl["vs_none"]
        if bases and max(bases.values()) - min(bases.values()) > 0.03:
            errors.append(f"Plans disagree on the no-transfers baseline (value - vs_none from {min(bases.values()):.2f} "
                          f"to {max(bases.values()):.2f}): the Planner's 'vs no transfers' would not match")
    for n in D.get("plan_notes") or []:
        if not n.endswith("dropped"):   # a move-count option dropped by the profit rule is normal, not a fault
            warnings.append(f"Plans: {n}")
    if plans:
        for mode, label in (("safe", "Play safe"), ("chase", "Chase rank")):
            if not any(k.startswith(mode + "_") for k in plans):
                warnings.append(f"No {label} plans this build (field ownership missing?): its Planner tab shows a 'no plan' message")
    D["health"] = {"checked": D["meta"].get("built"), "ok": not errors, "errors": errors[:50], "warnings": warnings}
    with open(path, "w") as f:
        json.dump(D, f, separators=(",", ":"))
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"validate: {len(D['players'])} players, GW{g}: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join("site", "data.json")))
