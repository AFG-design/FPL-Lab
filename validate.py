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
Warnings (printed, and saved in data.json "health" for the Health page; never fail the build):
  - before a deadline: history/deadline_gw{g}.json missing, stale, for other weeks or without your players
  - legacy data without squad_source evidence outside a required Free Hit restore
  - a player with 300+ minutes and no Understat row (and no manual override)
  - no betting odds for any of next gameweek's fixtures
  - once the current gameweek is finished, per-GW points not adding up to a player's FPL total (DD hauls column)
  - no season starts for any player (Points leaders Starts column)
  - last-6 goals or assists above the season figure
  - a gameweek in progress with no pre-deadline snapshot for the xP table's live column (meta.xp_cur), or a
    snapshot with fewer entries than half the players (it normally leaves out only players projected 0)
  - player odds (history/player_odds_gw*.json) for the latest finished-deadline gameweek missing a checkpoint
    (72, 24 or 3 h before the deadline), when that gameweek's file uses per-checkpoint snapshots. The model doesn't
    use player odds yet; this keeps the history complete for testing them. Skipped (not warned) when no file has
    snapshots, e.g. with no ODDS_API_KEY.
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


def is_bad(x):
    return x is None or type(x) not in (int, float) or math.isnan(x) or math.isinf(x)


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
            # the week is your actual points after hits against the model's highest projected score from what it
            # suggested (or, marked assumed, its best pick from your 15), rounded: the target
            tg_ = w.get("target") or {}
            cap_mult_ = 3 if tg_.get("basis") == "your 15" and w.get("chip") == "3xc" else 2
            if tg_.get("captain_multiplier", cap_mult_) != cap_mult_:
                errors.append(f"You vs the model GW{w['gw']}: target captain multiplier disagrees with its basis")
            ok_ = tg_.get("par") is not None and abs(tg_["par"] - tg_.get("exp", -999)) <= 0.5
            if tg_.get("basis") == "your 15":
                xp_ = {int(k): v for k, v in w.get("xp", {}).items()}
                m_ = w["model"]
                cnt_ = m_["xi"] + (m_["bench"] if w.get("chip") == "bboost" else [])
                exp_ = sum(xp_.get(i, 0) for i in cnt_) + (2 if w.get("chip") == "3xc" else 1) * xp_.get(m_["cap"], 0)
                ok_ = ok_ and tg_.get("assumed") is True and abs(tg_["exp"] - exp_) <= 0.2
            elif tg_.get("basis") == "suggested":
                ok_ = ok_ and len(tg_.get("xi", [])) == 11 and abs(tg_["exp"] - (tg_["xp"] - 4 * tg_["hits"])) <= 0.2
            else:
                ok_ = False
            if not ok_:
                errors.append(f"You vs the model GW{w['gw']}: target {tg_.get('basis')} {tg_.get('exp')}/{tg_.get('par')} doesn't add up")
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
        if nt_ and (len(nt_.get("xi", [])) != 11 or is_bad(nt_.get("par")) or is_bad(nt_.get("exp")) or abs(nt_["par"] - nt_["exp"]) > 0.5 or len(nt_.get("out", [])) != len(nt_.get("in", []))):
            errors.append(f"You vs the model: next week's target doesn't add up ({nt_.get('exp')}/{nt_.get('par')}, {len(nt_.get('xi', []))} in the XI)")
        for w in vm.get("weeks", []):
            t_ = w.get("target") or {}
            if t_.get("basis") == "suggested" and set(map(int, t_.get("xi_xp", {}))) != set(t_.get("xi", [])):
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

    # xP table live column: the gameweek in progress should have its pre-deadline projections
    xc = D["meta"].get("xp_cur")
    if xc and xc.get("status") != "snapshot":
        warnings.append(f'xP table GW{xc.get("gw")} live column has no projections ({xc.get("status")})')
    elif xc and xc.get("in_snapshot", 0) < 0.5 * len(D["players"]):
        warnings.append(f'xP table GW{xc["gw"]} live column: the snapshot has only {xc.get("in_snapshot", 0)} players '
                        f'for {len(D["players"])} listed; players not in it show 0')

    # odds for next gameweek
    odds = load(os.path.join(HERE, "odds", "odds.json")) or {}
    if g and not any(m.get("gw") == g and not m.get("played") for m in odds.get("matches", [])):
        warnings.append(f"No betting odds for any GW{g} fixture: fixture xG comes from team ratings only")

    # player odds history: the last gameweek whose deadline has passed should have all three checkpoints
    po = sorted(((int(f[len("player_odds_gw"):-5]), f) for f in os.listdir(os.path.join(HERE, "history"))
                 if f.startswith("player_odds_gw") and f.endswith(".json")), reverse=True)
    for pg, f in po:
        if pg >= g:   # the coming gameweek is still being collected
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
    # Planner strategy tabs (views/planner.js): each tab shows one optimiser plan per strategy. Every plan must name
    # players we list and field a legal XI; a strategy with no plans (build.py drops Play safe and Chase rank when the
    # field ownership file is missing) is a warning, and the tab says so instead of showing the Balanced plan.
    pids = {p["id"] for p in D["players"]}
    plans = D.get("plans") or {}
    if not plans:
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
    # strategy budgets (optimise.strategy_plans): Play safe never below Balanced, Chase rank at most chase_budget below,
    # and no plan with transfers short of the profit rule. A breach means the solver ignored its floor: stop the publish.
    rules = D.get("plan_rules") or {}
    if plans and not rules:
        warnings.append("plan_rules missing: the strategy budgets can't be checked")
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
        budget = {"balanced": 0.0, "safe": rules.get("safe_budget", 0.0), "chase": rules.get("chase_budget", 4.0)}[mode]
        if pl["vs_balanced"] < -(budget + rules.get("tie", 0.1) + 0.01):
            errors.append(f"Plan {k}: {pl['vs_balanced']:+.2f} vs Balanced, over its {budget:g}-point budget")
        nh = sum(wk.get("hits", 0) for wk in pl.get("weeks", []))
        cap = (rules.get("max_hits") or {}).get(mode)
        if cap is not None and any(wk.get("hits", 0) > cap for wk in pl.get("weeks", [])):
            errors.append(f"Plan {k}: takes more than {cap} hit(s) in a week ({mode} allows {cap})")
        if nh and rules.get("hit_gain") is not None and pl.get("hit_gain", -99) < rules["hit_gain"] * nh - 0.01:
            errors.append(f"Plan {k}: {nh} hit(s) gaining {pl.get('hit_gain', 'unknown')} vs no hits, short of the hit rule")
        moved = any(wk.get("in") for wk in pl.get("weeks", []))
        if moved and not k.endswith("roll") and pl["vs_none"] < rules.get("min_profit", 1.0) - 0.01:
            errors.append(f"Plan {k}: {pl['vs_none']:+.2f} vs no transfers, short of the profit rule")
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
