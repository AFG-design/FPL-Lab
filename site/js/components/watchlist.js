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
