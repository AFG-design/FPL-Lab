"""Which squad and bank the plans start from.

A Free Hit squad lasts one gameweek: FPL then restores the squad and bank from the week before. From the Free Hit
deadline until the next one, FPL's picks for the current GW are the temporary squad, while every plan for the next GW
must start from the restored one. The current GW's picks still drive live scores, rivals and review.
"""


def owned_picks(picks, picks_gw, next_gw, fetch):
    """Return (own_picks, squad_gw, fh_active).

    picks: FPL picks for picks_gw (None when the season hasn't started); fetch(gw) gets another GW's picks.
    Missing input: if the pre-Free-Hit picks can't be fetched, fetch raises and so does this, so the build fails
    rather than planning from the wrong squad. A Free Hit shown in GW1 (impossible in FPL) raises too.
    Ambiguous: a Free Hit GW with no next GW (GW38) has nothing to plan, so the picks are used as they are.
    """
    fh_active = bool(picks) and picks.get("active_chip") == "freehit" and next_gw is not None and next_gw > picks_gw
    if not fh_active:
        return picks, picks_gw, False
    if picks_gw <= 1:
        raise RuntimeError(f"Free Hit shown as active in GW{picks_gw}: no earlier squad to restore")
    return fetch(picks_gw - 1), picks_gw - 1, True


def team_value(own_picks, bank, now_cost, fh_active):
    """Team value as FPL shows it (bank plus current prices), in £m.

    After a Free Hit the pre-Free-Hit week's stored value is a week out of date, so it's worked out from today's prices
    (now_cost: {player id: price in tenths}); otherwise FPL's own figure is used as before.
    """
    if not own_picks:
        return 0.0
    if fh_active:
        return round(bank + sum(now_cost[p["element"]] for p in own_picks["picks"]) / 10, 1)
    return own_picks["entry_history"]["value"] / 10
