// Data health: when each source last updated, the recent refresh runs, and anything that failed.
function ageTxt(iso) {
  if (!iso) return "–";
  const m = (Date.now() - new Date(iso)) / 6e4;
  return m < 1 ? "just now" : m < 60 ? `${Math.round(m)} min ago` : m < 48 * 60 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} days ago`;
}
function vHealth() {
  const S_ = D.sources || {}, inPlay = !!(D.live && D.live.in_play && !D.live.finished);
  const ageH = iso => iso ? (Date.now() - new Date(iso)) / 36e5 : 1e9;
  const pill = (ok, warn) => ok ? '<span class="pill good">OK</span>' : warn ? '<span class="pill warn">Check</span>' : '<span class="pill bad">Problem</span>';
  const po = S_.player_odds, poErr = po?.error && po.error.at && (!po.built || po.error.at > po.built) ? po.error.message : null;
  const rows = [
    ["FPL data", S_.fpl?.built, `GW${S_.fpl?.gw} · ${S_.fpl?.players} players`, ageH(S_.fpl?.built) < (inPlay ? 0.5 : 1.5), ageH(S_.fpl?.built) < 3, inPlay ? "Every 10 minutes during matches, otherwise every 30" : "Every 30 minutes"],
    ["Understat shots", S_.understat?.built, S_.understat ? `${S_.understat.matches} matches · ${S_.understat.players} players matched (${S_.understat.unmatched} not)` : "", ageH(S_.understat?.built) < 6, ageH(S_.understat?.built) < 48, "New matches each refresh"],
    ["Match odds", S_.odds?.built, S_.odds ? `${S_.odds.matches} matches, ${S_.odds.upcoming} upcoming` : "", ageH(S_.odds?.built) < 6, ageH(S_.odds?.built) < 48, "football-data.co.uk, each refresh"],
    ["Player odds", po?.built, po ? `GW${po.gw} · ${po.fixtures} fixtures · ${po.credits_left ?? "–"} credits left${po.unmatched ? ` · ${po.unmatched} names unmatched` : ""}` : "Not collected", !!po && !poErr && po.gw >= (D.meta.cur_gw || 0), !!po, "Before each deadline (The Odds API)"],
    ["Ownership samples", S_.crowd?.built, S_.crowd ? `GW${S_.crowd.gw} · top 10k ${S_.crowd.top10k} · near you ${S_.crowd.near} · ladder ${S_.crowd.teams} · rivals ${S_.crowd.rivals}` : "", S_.crowd?.gw === D.meta.cur_gw, S_.crowd?.gw === D.meta.cur_gw - 1, "Once per gameweek, after the deadline"],
  ];
  const logs = [
    ["Price changes", `${S_.prices?.nights ?? 0} night${S_.prices?.nights === 1 ? "" : "s"} recorded`, "Stats → Prices track record"],
    ["Injury news", `${S_.news?.players ?? 0} players with a news history`, "Player panel → News history"],
    ["Injury status", S_.status?.gws?.length ? `GW${S_.status.gws.join(", GW")}` : "–", "Tells injured from dropped in the model"],
    ["Top-10k template", S_.template?.gws?.length ? `GW${S_.template.gws[0]}–${S_.template.gws[S_.template.gws.length - 1]}` : "–", "Review → Template tracker"],
  ];
  // recent refresh runs (public GitHub API, checked every 10 minutes)
  const runs = (HEALTH.runs || []).slice(0, 15);
  const trig = r => r.event === "schedule" ? "GitHub schedule" : r.event === "workflow_dispatch" ? "cron-job.org / Refresh button" : r.event === "push" ? "Site update" : r.event;
  const gaps = runs.slice(0, -1).map((r, k) => (new Date(r.created_at) - new Date(runs[k + 1].created_at)) / 6e4);
  const maxGap = gaps.length ? Math.max(...gaps) : null;
  const runRows = runs.map(r => `<tr><td>${ukTime(r.created_at)}</td><td>${esc(trig(r))}</td><td>${r.status !== "completed" ? '<span class="pill mut">Running</span>' : r.conclusion === "success" ? '<span class="pill good">Done</span>' : r.conclusion === "skipped" ? '<span class="pill mut">Skipped</span>' : `<span class="pill bad">${esc(r.conclusion || "failed")}</span>`}</td><td class="n">${r.updated_at && r.status === "completed" ? Math.max(1, Math.round((new Date(r.updated_at) - new Date(r.run_started_at || r.created_at)) / 6e4)) + " min" : "–"}</td><td><a href="${r.html_url}" target="_blank" rel="noopener">Log ↗</a></td></tr>`).join("");
  const A = D.accuracy?.absence || [];
  return `<div class="kpis" style="margin-bottom:16px">
      <div class="kpi"><span class="lbl">Site data</span><b>${ageTxt(D.meta.built)}</b><span class="delta muted">${ukTime(D.meta.built)}, took ${D.meta.build_secs ?? "–"}s</span></div>
      <div class="kpi"><span class="lbl">Last refresh run</span><b class="${HEALTH.last && HEALTH.last.conclusion !== "success" ? "down" : ""}">${HEALTH.last ? (HEALTH.last.conclusion === "success" ? "Worked" : esc(HEALTH.last.conclusion || "–")) : "–"}</b><span class="delta muted">${HEALTH.last ? ageTxt(HEALTH.last.updated_at) : "checking GitHub…"}</span></div>
      <div class="kpi"><span class="lbl">Longest gap between runs</span><b class="${maxGap > 45 ? "down" : ""}">${maxGap == null ? "–" : maxGap < 90 ? Math.round(maxGap) + " min" : (maxGap / 60).toFixed(1) + " h"}</b><span class="delta muted">over the last ${runs.length} runs</span></div>
    </div>
    <div class="panel"><h3>Sources</h3><div class="tablebox"><table><thead><tr><th>Source</th><th>Updated</th><th>Details</th><th>How often</th><th>Status</th></tr></thead><tbody>
      ${rows.map(([n, at, det, ok, warn, how]) => `<tr><td><b>${n}</b></td><td>${ageTxt(at)}</td><td class="muted">${esc(det)}</td><td class="muted">${how}</td><td>${pill(ok, warn)}</td></tr>`).join("")}</tbody></table></div>
      ${poErr ? `<p class="verdict" style="border-color:var(--bad);margin-top:10px">Player odds failed at ${ukTime(po.error.at)}: ${esc(poErr.slice(0, 160))}</p>` : ""}</div>
    <div class="grid2">
      <div class="panel"><h3>Recent refresh runs</h3>${runs.length ? `<div class="tablebox"><table><thead><tr><th>Started (UK)</th><th>Triggered by</th><th>Result</th><th class="n">Took</th><th></th></tr></thead><tbody>${runRows}</tbody></table></div>` : `<p class="muted">Couldn't reach GitHub just now. It's checked every 10 minutes.</p>`}
        <p class="note">Runs that take about a minute are the 10-minute checks outside match times: they look for live matches and stop without rebuilding.</p></div>
      <div class="panel"><h3>Logs being collected</h3><ul class="alerts">${logs.map(([n, v, w]) => `<li><span><b>${n}:</b> ${esc(v)} <span class="muted">· ${w}</span></span></li>`).join("")}</ul>
        ${A.length ? `<h3 style="margin:14px 0 6px">Injury-absence rule check</h3>${A.slice().reverse().map(a => `<div class="tablebox" style="margin-bottom:8px"><table><thead><tr><th>GW${a.gw}${a.done ? "" : " (in progress)"}</th><th class="n">xP with rule</th><th class="n">xP without</th><th class="n">Mins with / without</th><th class="n">Played</th><th class="n">Pts</th></tr></thead><tbody>${a.rows.map(r => `<tr><td><button data-p="${r.id}" class="pname linkish">${esc(P[r.id]?.name || r.id)}</button></td><td class="n">${f1(r.xp_fix)}</td><td class="n">${f1(r.xp_old)}</td><td class="n">${r.min_fix} / ${r.min_old}</td><td class="n">${r.mins == null ? "–" : r.mins + "'"}</td><td class="n">${r.pts ?? "–"}</td></tr>`).join("")}</tbody></table></div>${a.done && a.err_fix != null ? `<p class="note">Average miss: <b>${a.err_fix}</b> pts with the rule, ${a.err_old} without; minutes off by ${a.min_err_fix} vs ${a.min_err_old}.</p>` : ""}`).join("")}
          <p class="note">Players a regular starter missed with no flag after recent FPL news are treated as coming back from a knock. Scored automatically once each gameweek finishes.</p>` : ""}</div>
    </div>`;
}
