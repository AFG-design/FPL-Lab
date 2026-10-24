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
  return `${missesPanel()}${acc}${comparePanel()}<div class="panel" style="max-width:800px"><h2 style="margin-bottom:10px">How the projections work</h2>
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

/* ---------- the week's biggest misses, and what caused them ---------- */
function missesPanel() {
  const M = D.accuracy?.misses; if (!M || !M.length) return "";
  if (!M.some(m => m.gw === S.missGw)) S.missGw = M[M.length - 1].gw;
  const m = M.find(x => x.gw === S.missGw), mx = Math.max(...Object.values(m.blame), 1);
  const row = r => `<tr><td><button data-p="${r.id}" class="pname linkish">${esc(P[r.id]?.name || r.id)}</button>${MINE.has(r.id) ? ' <span class="tag">Yours</span>' : ""}</td><td class="n">${f1(r.xp)}</td><td class="n"><b>${r.pts}</b></td><td class="n ${r.miss > 0 ? "up" : "down"}">${sgn(r.miss)}</td><td>${esc(r.why)}</td></tr>`;
  const tbl = list => `<div class="tablebox"><table><thead><tr><th>Player</th><th class="n">xP</th><th class="n">Pts</th><th class="n">Miss</th><th>Main reason</th></tr></thead><tbody>${list.map(row).join("")}</tbody></table></div>`;
  return `<div class="panel"><div class="bar"><h2>Biggest misses</h2>
      <div class="seg" role="group" aria-label="Gameweek">${M.map(x => `<button data-missgw="${x.gw}" aria-pressed="${x.gw === m.gw}">GW${x.gw}</button>`).join("")}</div></div>
    <p class="note" style="margin-top:0">GW${m.gw} re-projected from the data before it, against what happened (${m.n} players, average miss ${m.mae.toFixed(2)} pts). The reason is the part of the score that differed most from the projection.</p>
    <span class="lbl">Where the error came from</span>
    <div class="capbars" style="margin:6px 0 14px">${Object.entries(m.blame).map(([k, v]) => `<div class="cb"><span class="pname">${esc(k)}</span><div class="track"><div class="fill" style="width:${v / mx * 100}%"></div></div><span class="val">${v}%</span></div>`).join("")}</div>
    <div class="statgrid"><div><h3 style="margin-bottom:8px">Scored less than projected</h3>${tbl(m.over)}</div><div><h3 style="margin-bottom:8px">Scored more than projected</h3>${tbl(m.under)}</div></div>
    <p class="note">Share of the total miss across all players, by part of the score. Attack misses (goals from low xG) are mostly luck; minutes misses are where better team news would help most.</p></div>`;
}

/* ---------- accuracy in the same terms other sites publish ---------- */
// FPL Review's Massive Data Model, one GW ahead, 2024/25 GW32-38 (RMSE), from Groos (2025), the OpenFPL paper
const PUBLISHED_RMSE = { zero: 0.69, blank: 1.19, ticker: 1.59, haul: 5.17 };
const BAND_NAMES = { zero: "Didn't play", blank: "Played, 2 pts or fewer", ticker: "3–4 pts", haul: "5+ pts" };
function comparePanel() {
  const C = D.accuracy?.compare; if (!C) return "";
  const m = C.all, b = C.base_all, d = v => v == null ? "–" : v.toFixed(2);
  const rows = Object.keys(BAND_NAMES).map(k => {
    const x = m.bands[k], y = b.bands[k], better = x.rmse != null && x.rmse <= PUBLISHED_RMSE[k];
    return `<tr><td>${BAND_NAMES[k]}</td><td class="n"><b>${d(x.rmse)}</b></td><td class="n">${PUBLISHED_RMSE[k].toFixed(2)}${better ? ' <span class="up">✓</span>' : ""}</td><td class="n">${d(y.rmse)}</td><td class="n">${x.bias == null ? "–" : sgn(x.bias)}</td><td class="n">${x.n.toLocaleString("en-GB")}</td></tr>`;
  }).join("");
  return `<div class="panel"><h2 style="margin-bottom:10px">Compared with other sites</h2>
    <p class="note" style="margin-top:0">The figures above only count players who played in the previous 3 gameweeks. Other sites usually score every player, including the many who sit out, which makes their average miss look smaller. These are the same re-run projections scored both ways.</p>
    <div class="kpis"><div class="kpi"><span class="lbl">Average miss, every player</span><b>${d(m.mae)}</b><span class="delta muted">recent-points average: ${d(b.mae)} · ${m.n.toLocaleString("en-GB")} player-weeks</span></div>
      <div class="kpi"><span class="lbl">Typical miss (RMSE), every player</span><b>${d(m.rmse)}</b><span class="delta muted">recent-points average: ${d(b.rmse)}</span></div>
      <div class="kpi"><span class="lbl">Average miss, recent players</span><b>${d(C.pool.mae)}</b><span class="delta muted">recent-points average: ${d(C.base_pool.mae)}</span></div></div>
    <h3 style="margin:16px 0 6px">Typical miss by outcome</h3>
    <div class="tablebox"><table><thead><tr><th>Outcome</th><th class="n">FPL Lab</th><th class="n">FPL Review</th><th class="n">Recent-points avg</th><th class="n">FPL Lab bias</th><th class="n">Player-weeks</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">Lower is better; ✓ marks a band where FPL Lab's miss is no bigger than FPL Review's. Bias is projected minus actual: positive means the model expected more. FPL Review's figures are published results from an independent test on 2024/25 GW32–38 (Groos, 2025, the OpenFPL paper), so this is a guide, not a head-to-head. The re-run uses no injury flags, which inflates the "Didn't play" and low-score misses compared with the live projections.</p></div>`;
}
