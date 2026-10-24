// Player watchlist (starred players) and injury news history.
const STARS = (() => { const s = store.get("fpl.stars"); return s && s.ids ? s : { ids: {}, updated: 0 }; })();
const isStarred = id => !!STARS.ids[id];
function toggleStar(id) {
  if (STARS.ids[id]) delete STARS.ids[id]; else STARS.ids[id] = { at: Date.now(), price: P[id]?.price };
  STARS.updated = Date.now(); store.set("fpl.stars", STARS); syncPush();
}
function mergeStars(remote) {   // called by sync: the newer list wins
  if (remote && remote.ids && (remote.updated || 0) > STARS.updated) { STARS.ids = remote.ids; STARS.updated = remote.updated; store.set("fpl.stars", STARS); return true; }
  return false;
}

/* ---------- news history ---------- */
const STATUS_WORD = { a: "Available", d: "Doubtful", i: "Injured", s: "Suspended", u: "Unavailable", n: "Not in squad" };
const agoTxt = iso => {
  const h = (Date.now() - new Date(iso)) / 36e5;
  return h < 1 ? `${Math.max(1, Math.round(h * 60))} min ago` : h < 24 ? `${Math.round(h)}h ago` : h < 24 * 14 ? `${Math.round(h / 24)}d ago` : new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
};
const ukWhen = iso => new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
const newsCls = st => st === "a" ? "good" : st === "d" ? "warn" : "bad";
function newsLine([status, chance, text]) {
  return text ? esc(text) : status === "a" ? "Fit: no news" : STATUS_WORD[status] || status;
}
function newsTimeline(p) {
  const h = p.newsh; if (!h || !h.length) return "";
  return `<section class="ph-sec"><h3>News history</h3><ol class="newsline">${h.slice().reverse().map(([t, st, ch, tx]) => `<li class="${newsCls(st)}"><time datetime="${t}">${ukWhen(t)}</time><span>${newsLine([st, ch, tx])}${ch != null && st !== "a" && !/chance/.test(tx || "") ? ` · ${ch}% chance` : ""}</span></li>`).join("")}</ol>
    <p class="note">Every change to his FPL status and news since we started recording (22 Oct 2026). Times are when FPL posted it.</p></section>`;
}
// news for the players you care about: your squad, planned signings and your watchlist
function newsFor(days = 7) {
  const care = new Set([...MINE, ...SB.moves.map(m => m.in), ...Object.keys(STARS.ids).map(Number)]);
  const cut = Date.now() - days * 864e5;
  return (D.news || []).filter(([t, id]) => care.has(id) && new Date(t) >= cut);
}

/* ---------- Home: watchlist and news ---------- */
function starsPanel() {
  const g = D.meta.next_gw, ids = Object.keys(STARS.ids).map(Number).filter(i => P[i]);
  const news = newsFor();
  if (!ids.length && !news.length) return `<div class="panel"><h3>Watchlist</h3><p class="muted" style="margin:0">Nobody on your radar yet. Star a player from his info panel to keep tabs on him.</p></div>`;
  const rows = ids.sort((a, b) => xpFrom(b, g, 5) - xpFrom(a, g, 5)).map(i => {
    const p = P[i], s = STARS.ids[i], dp = s.price != null ? Math.round((p.price - s.price) * 10) / 10 : 0;
    const pr = p.price_proj?.[0], last = p.newsh?.[p.newsh.length - 1], fresh = last && Date.now() - new Date(last[0]) < 3 * 864e5;
    return `<tr><td><button data-p="${i}" class="pname linkish">${esc(p.name)}</button> <span class="muted">${T[p.team].short} ${p.pos}</span>${p.status !== "a" ? ` <span class="pill ${p.status === "d" ? "warn" : "bad"}">${p.chance ?? 0}%</span>` : ""}${fresh ? ` <span class="pill mut" title="${esc(newsLine(last.slice(1)))}">news ${agoTxt(last[0])}</span>` : ""}</td>
      <td class="n">${p.price.toFixed(1)}${dp ? ` <span class="${dp > 0 ? "up" : "down"}">${dp > 0 ? "▲" : "▼"}${Math.abs(dp).toFixed(1)}</span>` : ""}</td>
      <td class="n ${pr >= 75 ? "up" : pr <= -75 ? "down" : "muted"}">${pr != null ? `${pr.toFixed(0)}%` : "–"}</td>
      <td><span class="fx">${fxChips(p, g, 3)}</span></td><td class="n"><b>${f1(xpg(i, g))}</b></td><td class="n">${f1(xpFrom(i, g, 5))}</td></tr>`;
  }).join("");
  return `<div class="panel"><div class="bar"><h3>Watchlist</h3><span class="muted">${ids.length} player${ids.length === 1 ? "" : "s"}</span></div>
    ${ids.length ? `<div class="tablebox"><table><thead><tr><th>Player</th><th class="n">£m</th><th class="n">Price</th><th>Next 3</th><th class="n">xP GW${g}</th><th class="n">Next 5</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="note">Price arrows show the change since you starred him; the % is FPL's progress towards tonight's price change.</p>` : `<p class="muted">Nobody on your radar yet. Star a player from his info panel to keep tabs on him.</p>`}
    ${news.length ? `<h3 style="margin:14px 0 6px">News this week</h3><ul class="alerts">${news.slice(0, 10).map(([t, id, prev, cur]) => `<li class="${newsCls(cur[0])}"><span><button data-p="${id}" class="pname linkish">${esc(P[id].name)}</button>${MINE.has(id) ? ' <span class="tag">Yours</span>' : isStarred(id) ? ' <span class="tag">★</span>' : ' <span class="tag">Plan</span>'}: ${newsLine(cur)}${prev ? ` <span class="muted">(was ${newsLine(prev).toLowerCase()})</span>` : ""} <span class="muted">· ${agoTxt(t)}</span></span></li>`).join("")}</ul>` : ""}</div>`;
}
