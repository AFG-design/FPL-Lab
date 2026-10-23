// Live gameweek mode (Home, while matches are on) and the week's deadline tracker.
/* ---------- live points with automatic subs and provisional bonus ---------- */
function liveState() {
  const L = D.live; if (!L || !L.rows || !L.fixtures) return null;
  const fxOf = tid => L.fixtures.filter(f => f.h === tid || f.a === tid);
  const status = tid => { const f = fxOf(tid); if (!f.length) return "blank"; if (f.every(x => x.done)) return "done"; return f.some(x => x.started) ? "playing" : "to play"; };
  const rows = L.rows.map(r => ({ ...r, st: status(r.team), live: r.pts + (r.prov || 0) }));
  const xi = rows.filter(r => r.pos <= 11), bench = rows.filter(r => r.pos > 11).sort((a, b) => a.pos - b.pos);
  const subs = [];
  if (L.chip !== "bboost") {
    // FPL's rule: a starter who didn't play is replaced by the first bench player who did, if the formation still works
    const valid = list => { const c = { GKP: 0, DEF: 0, MID: 0, FWD: 0 }; list.forEach(r => c[P[r.id]?.pos]++); return c.GKP === 1 && c.DEF >= 3 && c.MID >= 2 && c.FWD >= 1; };
    let team = xi.slice();
    for (const out of xi.filter(r => r.mins === 0 && (r.st === "done" || r.st === "blank"))) {
      const isGK = P[out.id]?.pos === "GKP";
      const cand = bench.find(b => !subs.some(s => s.in === b) && (isGK ? P[b.id]?.pos === "GKP" : P[b.id]?.pos !== "GKP") && (b.mins > 0 || b.st === "playing") &&
        valid(team.filter(r => r !== out).concat(b)));
      if (cand) { team = team.filter(r => r !== out).concat(cand); subs.push({ out, in: cand, sure: cand.mins > 0 }); }
    }
    xi.splice(0, xi.length, ...team);
  } else xi.push(...bench.splice(0));
  // captain: if he didn't play, the vice gets the armband
  const cap = rows.find(r => r.cap), vice = rows.find(r => r.vice);
  const capOut = cap && cap.mins === 0 && (cap.st === "done" || cap.st === "blank");
  const mult = r => r.cap ? (capOut ? 1 : (L.chip === "3xc" ? 3 : 2)) : r.vice && capOut && r.mins > 0 ? (L.chip === "3xc" ? 3 : 2) : 1;
  const total = xi.reduce((a, r) => a + r.live * mult(r), 0) - (L.hits || 0);
  const left = xi.filter(r => r.st === "to play").length, playing = xi.filter(r => r.st === "playing").length;
  // field: effective ownership x live points (with provisional bonus)
  const F = D.crowd && D.crowd.gw === L.gw ? D.crowd : null, all = L.pts_all || {};
  const fieldAvg = src => src ? Object.entries(src.eo).reduce((a, [i, e]) => a + e / 100 * (all[i] || 0), 0) : null;
  return { L, rows, xi, bench: rows.filter(r => !xi.includes(r)), subs, cap, vice, capOut, mult, total, left, playing,
    top10k: F ? fieldAvg(F.top10k) : null, near: F && F.near?.n >= 100 ? fieldAvg(F.near) : null };
}
function livePanel() {
  const L = D.live; if (!L || L.finished || !L.in_play) return "";
  const s = liveState(); if (!s) return "";
  const stTxt = { done: "Finished", playing: "Playing", "to play": "Yet to play", blank: "No game" };
  const row = r => `<tr class="${s.xi.includes(r) ? "" : "lv-bench"}"><td><button data-p="${r.id}" class="pname linkish">${esc(P[r.id]?.name || r.id)}</button>${r.cap && !s.capOut ? ' <span class="pill warn">C</span>' : ""}${r.vice && s.capOut && r.mins > 0 ? ' <span class="pill warn">C (vice)</span>' : r.vice ? ' <span class="pill mut">V</span>' : ""}</td>
    <td><span class="lv-st lv-${r.st.replace(" ", "")}">${stTxt[r.st]}</span></td><td class="n">${r.mins}'</td><td class="n">${r.bps}</td><td class="n">${r.prov ? `<b class="up">+${r.prov}</b>` : r.bonus ? r.bonus : "–"}</td><td class="n"><b>${s.xi.includes(r) ? r.live * s.mult(r) : r.live}</b></td></tr>`;
  const vs = (lbl, v) => v == null ? "" : `<div class="kpi"><span class="lbl">${lbl}</span><b>${f1(v)}</b><span class="delta ${s.total >= v ? "up" : "down"}">you're ${f1(Math.abs(s.total - v))} ${s.total >= v ? "ahead" : "behind"}</span></div>`;
  const fx = L.fixtures.slice().sort((a, b) => (a.ko || "").localeCompare(b.ko || ""));
  return `<div class="panel live-panel"><div class="bar"><h2><span class="live-dot" aria-hidden="true"></span>GW${L.gw} live</h2><span class="muted">updated ${new Date(D.meta.built).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" })}</span></div>
    <div class="kpis" style="margin-bottom:12px">
      <div class="kpi"><span class="lbl">Your live points</span><b style="font-size:32px">${s.total}</b><span class="delta muted">${s.left} yet to play · ${s.playing} playing${L.hits ? ` · −${L.hits} hit` : ""}</span></div>
      ${vs("Top-10k average", s.top10k)}${vs("Managers around you", s.near)}
      ${L.average ? `<div class="kpi"><span class="lbl">Overall average</span><b>${L.average}</b><span class="delta muted">from FPL</span></div>` : ""}
    </div>
    ${s.subs.length ? `<ul class="alerts" style="margin-bottom:10px">${s.subs.map(x => `<li class="good"><span>Auto-sub: <b>${esc(P[x.in.id]?.name)}</b> on for ${esc(P[x.out.id]?.name)}${x.sure ? "" : " (if he plays)"}.</span></li>`).join("")}${s.capOut ? `<li class="warn"><span>${esc(P[s.cap.id]?.name)} didn't play: the armband passes to ${esc(P[s.vice?.id]?.name || "your vice")}.</span></li>` : ""}</ul>` : ""}
    <div class="tablebox"><table><thead><tr><th>Player</th><th>Status</th><th class="n">Mins</th><th class="n">${term("bps", "BPS")}</th><th class="n">Bonus</th><th class="n">Pts</th></tr></thead><tbody>${s.xi.map(row).join("")}${s.bench.map(row).join("")}</tbody></table></div>
    <div class="lv-fx">${fx.map(f => `<span class="${f.done ? "done" : f.started ? "on" : ""}" title="${f.ko ? ukTime(f.ko) : ""}">${T[f.h].short} ${f.started ? `${f.hs ?? 0}–${f.as ?? 0}` : "v"} ${T[f.a].short}${f.started && !f.done ? ` <small>${f.mins}'</small>` : ""}</span>`).join("")}</div>
    <p class="note">Bonus in green is provisional: the top 3 BPS in each match as it stands. Auto-subs follow FPL's rules once a starter's game is over. The field averages use their teams from this gameweek. Updates every 10 minutes during matches (GitHub can run a few minutes late). <button class="linkish" data-v-go="rivals">Live mini-league table →</button></p></div>`;
}

/* ---------- Deadlines tab: countdown, this week's timeline, every deadline ahead ---------- */
function weekTimeline() {
  const W = D.week; if (!W) return "";
  const now = Date.now(), mine = new Set(D.squad.map(s => P[s.id]?.team));
  const items = [[W.deadline, "deadline", `<b>GW${W.gw} deadline</b> · ${countdown(W.deadline)} left`]];
  W.price_updates.forEach(d => items.push([d, "price", `Price changes <span class="muted">(from about ${new Date(d).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" })})</span>`]));
  W.fixtures.forEach(([ko, h, a]) => items.push([ko, "ko", `<button data-team="${h}" class="linkish">${T[h].name}</button> v <button data-team="${a}" class="linkish">${T[a].name}</button>${mine.has(h) || mine.has(a) ? ' <span class="tag">your players</span>' : ""}`]));
  W.europe.forEach(([c, d, ts]) => items.push([d + "T18:00:00Z", "eu", `${c}: ${ts.map(t => T[t]?.short).join(", ")}${ts.some(t => mine.has(t)) ? ' <span class="tag">your players</span>' : ""}`]));
  items.sort((x, y) => x[0].localeCompare(y[0]));
  const day = iso => new Date(iso).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short", timeZone: "Europe/London" });
  const time = (iso, k) => k === "eu" ? "Evening" : new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
  let lastDay = "";
  return `<ul class="week-list">${items.filter(x => new Date(x[0]).getTime() > now - 2 * 36e5).map(([iso, k, t]) => { const d = day(iso), head = d !== lastDay ? `<li class="wk-day">${d}</li>` : ""; lastDay = d;
    return `${head}<li class="wk-${k}"><time>${time(iso, k)}</time><span>${t}</span></li>`; }).join("")}</ul>`;
}
function vDeadlines() {
  const W = D.week;
  if (!W) return stateView({ title: "No deadline ahead", body: "The season's deadlines will appear here once FPL publishes the next gameweek." });
  const g = W.gw, nx = W.fixtures[0], ahead = (W.deadlines || []).slice(0, 8);
  const days = iso => Math.round((new Date(iso) - Date.now()) / 864e5);
  return `<div class="grid2">
    <div style="display:grid;gap:20px;align-content:start;min-width:0">
      <div class="panel dl-hero"><span class="lbl">GW${g} deadline</span><b id="dlCount">${countdown(W.deadline)}</b><span>${ukTime(W.deadline)}</span>
        ${nx ? `<span class="muted">First kick-off ${ukTime(nx[0])}: ${T[nx[1]].name} v ${T[nx[2]].name}</span>` : ""}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px"><button class="btn primary" data-howto="${g}">Make these moves on FPL</button><button class="btn" data-ics="1">Add all deadlines to calendar</button></div></div>
      <div class="panel"><h3>Coming up</h3><div class="tablebox"><table><thead><tr><th>Gameweek</th><th>Deadline (UK)</th><th class="n">In</th></tr></thead>
        <tbody>${ahead.map(([gw, d]) => `<tr><td>GW${gw}</td><td>${ukTime(d)}</td><td class="n">${new Date(d) - Date.now() < 864e5 ? countdown(d) : days(d) + " day" + (days(d) === 1 ? "" : "s")}</td></tr>`).join("")}</tbody></table></div>
        <p class="note">The calendar file adds every remaining deadline, each with reminders 24 hours and 2 hours before. Open it on your phone to import it.</p></div>
    </div>
    <div class="panel"><h3>This week</h3>${weekTimeline()}
      <p class="note">UK times. Price changes happen once a night, shortly after the time shown. European games are flagged for rotation risk. Tap a team for its profile.</p></div>
  </div>`;
}
// an .ics file with every remaining deadline, each with reminders 24 hours and 2 hours before
function deadlinesICS() {
  const stamp = d => new Date(d).toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  const ev = (D.week?.deadlines || []).map(([gw, d]) => ["BEGIN:VEVENT", `UID:fpl-lab-gw${gw}-${stamp(d)}@afg-design.github.io`, `DTSTAMP:${stamp(Date.now())}`,
    `DTSTART:${stamp(d)}`, `DTEND:${stamp(new Date(d).getTime() + 15 * 6e4)}`, `SUMMARY:FPL GW${gw} deadline`, "DESCRIPTION:https://afg-design.github.io/FPL-Lab/",
    "BEGIN:VALARM", "TRIGGER:-PT24H", "ACTION:DISPLAY", `DESCRIPTION:FPL GW${gw} deadline in 24 hours`, "END:VALARM",
    "BEGIN:VALARM", "TRIGGER:-PT2H", "ACTION:DISPLAY", `DESCRIPTION:FPL GW${gw} deadline in 2 hours`, "END:VALARM", "END:VEVENT"].join("\r\n"));
  const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FPL LAB//Deadlines//EN", "CALSCALE:GREGORIAN", ...ev, "END:VCALENDAR"].join("\r\n");
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" })); a.download = "fpl-deadlines.ics";
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
