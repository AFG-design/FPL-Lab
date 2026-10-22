// Tap-to-explain terms.
/* ---------- tap-to-explain ---------- */
const GLOSS = {
  xp: ["xP (projected points)", "The points the model expects a player to score, averaged over all the ways a match can go. 4–5 is a strong week for most players."],
  xgi: ["xGI", "Expected goal involvement: expected goals (xG) plus expected assists (xA). It measures the quality of chances a player gets or creates, regardless of whether they went in. Per 90 = per full match."],
  eo: ["EO (effective ownership)", "The share of managers who own a player, with captains counted twice. A player at 150% EO gains the field 1.5 points for every point he scores, so if you don't own him, you lose ground when he does well."],
  nailed: ["Nailed", "How sure a player is to start and play most of the game, from 0 to 100. It uses his recent starts, how long he plays and any injury flag. 85+ is nailed on; under 60 is a rotation risk."],
  spread: ["Spread vs field", "How far your score typically lands from the managers around your rank in a gameweek. ±5 means you'll usually be within about 5 points of them. Lower is safer; higher is riskier, but gives you more chance to climb."],
  swing: ["Swing", "How much a player's projected points move you against the field: your share of his points minus theirs. A negative swing means the field gains on you if he delivers."],
  bps: ["BPS (bonus point system)", "FPL's in-match score for every action: goals, key passes, tackles, saves and more. The top 3 BPS in each match earn 3, 2 and 1 bonus points."],
  bigchance: ["Big chance", "A shot worth 0.3 xG or more: a clear chance a player would usually be expected to score, such as a one-on-one or a close-range header. Opta's own definition is similar."],
  inbox: ["Shots in the box", "Shots taken from inside the penalty area, where most goals come from. More reliable than total shots, which include long-range efforts."],
  created: ["Chances created", "Shots a player set up with a pass (key passes). Big chances created are those worth 0.3 xG or more."],
  ft: ["Free transfers", "You get 1 a week and can bank up to 5. Moves beyond your free transfers cost 4 points each (a hit)."],
  hit: ["Hit", "A transfer beyond your free ones costs 4 points. Worth it only if the new player outscores the old one by more than 4 over the weeks you keep him."],
  dc: ["Defensive contributions (DC)", "2 points for reaching a defensive threshold in a match: 10 clearances, blocks, interceptions and tackles for defenders, or 12 (including recoveries) for midfielders and forwards."],
  xmins: ["xMins", "Expected minutes next gameweek, from recent starts and FPL's chance-of-playing flag."],
  verdict: ["Verdicts", "Strong: a clear gain worth acting on. Marginal: a small edge. Coin flip: the options are too close for the model to call, so go with your judgement. Safe pick: what most managers around your rank are doing."],
  strategy: ["Strategy", "Balanced maximises your projected points. Play safe sticks closer to what managers around your rank own. Chase rank goes for differentials: more swing, up or down."],
  strength: ["Team strength %", "From the model's attack and defence ratings. Strength = share of the available points (3 a game) a team would expect against an average side on a neutral ground: 50% is mid-table, 70%+ is title form. Attack = goals scored vs the league average (120% = 20% more). Defence = how few they concede vs average (120% = concede about a sixth less)."],
  gap: ["Gap", "How many total points each manager is ahead of you (+) or behind you (−)."],
  chipsleft: ["Chips left", "Each manager's chips for this half of the season (GW1–19, then a new set from GW20): WC Wildcard, FH Free Hit, BB Bench Boost, TC Triple Captain. Greyed out = already used. A rival with Triple Captain or Bench Boost left can make up a lot of ground in one week."],
  horizon: ["Plan length", "How many gameweeks the planner, suggestions and Re-plan look ahead. 3 GWs favours players with good short-term fixtures. 6 GWs favours longer-term value and fewer hits. Moves after the last gameweek are kept but don't count."],
  l4: ["L4 / L6", "Over the last 4 or 6 gameweeks. Recent form, which reacts faster to changes in role or team than whole-season numbers."],
};
function term(key, label) { return `<button type="button" class="term" data-term="${key}">${label ?? GLOSS[key]?.[0] ?? key}</button>`; }
function showTerm(btn) {
  const g = btn.dataset.fxtip ? [btn.dataset.fxtip.split(":")[0], btn.dataset.fxtip.slice(btn.dataset.fxtip.indexOf(":") + 1).trim()] : GLOSS[btn.dataset.term]; if (!g) return;
  let tip = $("#tip");
  if (!tip) { tip = document.createElement("div"); tip.id = "tip"; tip.setAttribute("role", "dialog"); document.body.appendChild(tip); }
  tip.innerHTML = `<b>${esc(g[0])}</b><p>${esc(g[1])}</p>`;
  tip.hidden = false;
  const r = btn.getBoundingClientRect(), w = Math.min(320, innerWidth - 32);
  tip.style.width = w + "px";
  tip.style.left = Math.max(16, Math.min(innerWidth - w - 16, r.left)) + "px";
  const below = r.bottom + 8, h = tip.offsetHeight;
  tip.style.top = (below + h > innerHeight - 12 ? Math.max(12, r.top - h - 8) : below) + "px";
}
document.addEventListener("click", e => {
  const t = e.target.closest(".term, [data-fxtip]");
  if (t) { e.preventDefault(); e.stopPropagation(); showTerm(t); return; }
  const tip = $("#tip"); if (tip && !tip.hidden && !e.target.closest("#tip")) tip.hidden = true;
}, true);
document.addEventListener("keydown", e => { if (e.key === "Escape") { const tip = $("#tip"); if (tip) tip.hidden = true; } });
addEventListener("scroll", () => { const tip = $("#tip"); if (tip) tip.hidden = true; }, { passive: true });
