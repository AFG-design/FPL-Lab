// Model accuracy.
/* ---------- Model ---------- */
function vModel() {
  const A = D.accuracy;
  const acc = A ? `<div class="panel"><h2 style="margin-bottom:10px">How accurate is it?</h2>
    <p>Each finished gameweek (GW${A.gws[0]}–${A.gws[A.gws.length - 1]}) was projected again using only the data available before it, then compared with the real points of ${A.n.toLocaleString("en-GB")} player appearances.</p>
    <div class="kpis"><div class="kpi"><span class="lbl">Correlation with real points</span><b>${A.corr.toFixed(2)}</b><span class="delta muted">recent-points average: ${A.base_corr.toFixed(2)}</span></div>
      <div class="kpi"><span class="lbl">Typical miss (RMSE)</span><b>${A.rmse.toFixed(2)}</b><span class="delta muted">recent-points average: ${A.base_rmse.toFixed(2)}</span></div>
      <div class="kpi"><span class="lbl">Average miss</span><b>${A.mae.toFixed(2)}</b><span class="delta muted">points per player per GW</span></div></div>
    <h3 style="margin:16px 0 6px">Calibration</h3><p class="note" style="margin-top:0">When the model says a player will score about X, how many did players actually score on average?</p>
    <div class="tablebox"><table><thead><tr><th>Projected</th><th class="n">Players</th><th class="n">Avg projected</th><th class="n">Avg actual</th></tr></thead><tbody>${A.buckets.map(([b, c, px, pa]) => `<tr><td>${b}–${b + 1} pts</td><td class="n">${c}</td><td class="n">${px.toFixed(2)}</td><td class="n">${pa.toFixed(2)}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Single-gameweek FPL points are very noisy: a correlation around 0.4 is about as good as public models get. The value is in ranking players sensibly and avoiding bad bets, not in calling exact scores.</p></div>
    ${A.weeks && A.weeks.length ? `<div class="panel"><h3>Week by week</h3>
      <p class="note" style="margin-top:0"><b>Re-run</b> = the current model projecting each past week from data before it. <b>Live</b> = the projections actually shown before the deadline, saved each week from GW8, next to FPL's own projected points for the same players.</p>
      ${lineChart([{ cls: "s1", vals: A.weeks.map(w => w.corr) }, { cls: "s2", vals: A.weeks.map(w => w.live?.corr ?? null) }, { cls: "s4", vals: A.weeks.map(w => w.live?.fpl_corr ?? null), dash: true }], A.weeks.map(w => "GW" + w.gw), { h: 170, yfmt: v => v.toFixed(1) })}
      <div class="legend"><span><i class="s1"></i>Re-run</span><span><i class="s2"></i>Live</span><span><i class="s4"></i>FPL's own (live)</span></div>
      <div class="tablebox" style="margin-top:10px"><table><thead><tr><th>GW</th><th class="n">Players</th><th class="n">Correlation</th><th class="n">Avg miss</th><th class="n">Top 30: projected → actual</th><th class="n">Live corr</th><th class="n">FPL's corr</th><th class="n">Live miss / FPL's</th></tr></thead>
      <tbody>${A.weeks.slice().reverse().map(w => `<tr><td>GW${w.gw}</td><td class="n">${w.n}</td><td class="n"><b>${w.corr.toFixed(2)}</b></td><td class="n">${w.mae.toFixed(2)}</td><td class="n">${w.top_pred.toFixed(1)} → ${w.top_act.toFixed(1)}</td><td class="n">${w.live?.corr != null ? w.live.corr.toFixed(2) : "–"}</td><td class="n">${w.live?.fpl_corr != null ? w.live.fpl_corr.toFixed(2) : "–"}</td><td class="n">${w.live?.mae != null ? `${w.live.mae.toFixed(2)} / ${w.live.fpl_mae.toFixed(2)}` : "–"}</td></tr>`).join("")}</tbody></table></div>
      <p class="note">Live figures start from GW8, the first week the snapshot was saved before the deadline.</p></div>` : ""}` : "";
  return `${acc}<div class="panel" style="max-width:800px"><h2 style="margin-bottom:10px">How the projections work</h2>
  <ul>
    <li><b>Team strength.</b> Attack and defence ratings from expected goals for and against in every match (70%) plus real goals (30%). They're adjusted for the opponents each team has faced and for home advantage, and pulled towards average while the sample is small.</li>
    <li><b>Betting markets.</b> Team ratings blend 70% from betting-market odds on every match so far with 30% from xG. When a fixture's own odds are published (usually a few days before), its projected goals come 85% from those odds. Odds are from football-data.co.uk${D.meta.odds ? ` (${D.meta.odds.matches} matches, ${D.meta.odds.upcoming} upcoming)` : ""}. In testing on GW3–7 this lifted the correlation with real points from 0.40 to 0.42.</li>
    <li><b>Fixtures.</b> Projected goals = league average (${D.meta.league_goals}) × attack × opponent defence × home/away. Clean-sheet and goals-conceded chances come from that, calibrated to real clean-sheet rates.</li>
    <li><b>Minutes.</b> How often a player starts or comes off the bench, and how long they play, over the last 5 gameweeks (recent games count more), times FPL's chance-of-playing flag.</li>
    <li><b>Player output.</b> xG and xA per 90 this season (recent games count more), blended with ${D.meta.priors_season || "last season"} and the two seasons before it, plus a positional average. First-choice penalty takers get a small boost. Assists are scaled up because FPL awards more assists than xA counts.</li>
    <li><b>Defensive contributions.</b> The chance of reaching the CBIT threshold, from each player's hit rate and their per-90 rate.</li>
    <li><b>Calibration.</b> The raw projections are adjusted so that, across past gameweeks, projected and real averages match (see the table above).</li>
    <li><b>Transfer plans.</b> An optimiser plans the next 5 gameweeks together: transfers, lineups and captains, within budget, squad shape, the 3-per-club rule and free-transfer rules. A banked free transfer is valued at 1.5 points.</li>
  </ul>
  <p class="note">Selling prices and free transfers are estimated from your public transfer history, because FPL only shows exact values when you're signed in. The model and data are updated every 30 minutes.</p></div>`;
}
