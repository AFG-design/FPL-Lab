// Live scores: every match this gameweek as a card, with badges, score, minute, scorers and your players.
function scoresStrip() {
  const L = D.live; if (!L || !L.fixtures?.length) return "";
  const now = Date.now(), soon = L.fixtures.some(f => !f.done);
  // show while the gameweek is on, and its results until the next deadline
  if (!soon && D.meta.deadline && new Date(D.meta.deadline) < now) return "";
  const mineRows = L.rows || [], myTeams = new Set(mineRows.filter(r => r.pos <= 11).map(r => r.team));
  const fx = L.fixtures.slice().sort((a, b) => (a.ko || "").localeCompare(b.ko || ""));
  const day = iso => new Date(iso).toLocaleDateString("en-GB", { weekday: "short", timeZone: "Europe/London" });
  const time = iso => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
  const live = fx.filter(f => f.started && !f.done).length;
  const card = f => {
    const st = f.done ? "ft" : f.started ? "live" : "pre";
    const status = st === "live" ? `<span class="mc-live"><i aria-hidden="true"></i>LIVE ${f.mins ? f.mins + "'" : ""}</span>` : st === "ft" ? `<span class="mc-ft">FT</span>` : `<span class="mc-pre">${day(f.ko)} ${time(f.ko)}</span>`;
    const side = s => {
      const tid = s === "h" ? f.h : f.a, sc = s === "h" ? f.hs : f.as, other = s === "h" ? f.as : f.hs;
      const win = st !== "pre" && sc != null && other != null && sc > other;
      return `<div class="mc-team ${win && st === "ft" ? "win" : ""}"><button data-team="${tid}" class="mc-club">${badge(tid, 28)}<span>${esc(T[tid].name)}</span></button><b class="mc-sc">${st === "pre" ? "" : sc ?? 0}</b></div>`;
    };
    const ev = (f.ev || []);
    const goals = s => ev.filter(e => e[1] === s && (e[0] === "g" || e[0] === "og")).map(e => `${esc(e[2])}${e[3] > 1 ? ` ×${e[3]}` : ""}${e[0] === "og" ? " (og)" : ""}`);
    const reds = ev.filter(e => e[0] === "r").map(e => esc(e[2]));
    const gh = goals("h"), ga = goals("a");
    const evHTML = gh.length || ga.length || reds.length ? `<div class="mc-ev">${gh.length || ga.length ? `<div><span>${gh.join(", ") || "&nbsp;"}</span><span>${ga.join(", ") || "&nbsp;"}</span></div>` : ""}${reds.length ? `<p class="mc-red">Red card: ${reds.join(", ")}</p>` : ""}</div>` : "";
    const mine = mineRows.filter(r => (r.team === f.h || r.team === f.a) && r.pos <= 11);
    const mineHTML = mine.length ? `<div class="mc-mine">${mine.map(r => `<button data-p="${r.id}" class="mc-p">${esc(P[r.id]?.name || r.id)}${r.cap ? " (C)" : ""}<b>${st === "pre" ? "–" : (r.pts + (r.prov || 0)) * (r.cap ? (L.chip === "3xc" ? 3 : 2) : 1)}</b></button>`).join("")}</div>` : "";
    return `<article class="mcard ${st} ${myTeams.has(f.h) || myTeams.has(f.a) ? "mine" : ""}" aria-label="${esc(T[f.h].name)} ${st === "pre" ? "v" : `${f.hs ?? 0}–${f.as ?? 0}`} ${esc(T[f.a].name)}">
      <div class="mc-top">${status}${myTeams.has(f.h) || myTeams.has(f.a) ? '<span class="mc-tag">Your players</span>' : ""}</div>
      ${side("h")}${side("a")}${evHTML}${mineHTML}</article>`;
  };
  return `<section class="scores" aria-label="GW${L.gw} scores">
    <div class="bar" style="margin:0 0 8px"><h2>GW${L.gw} scores${live ? ` <span class="pill good">${live} live</span>` : ""}</h2><span class="muted">${soon ? "updates every 10 minutes during matches" : "final scores"}</span></div>
    <div class="score-rail" id="scoreRail">${fx.map(card).join("")}</div></section>`;
}
// on phones, scroll the rail so the first live or upcoming match is in view
function railToNow() {
  const r = $("#scoreRail"); if (!r || r.scrollWidth <= r.clientWidth) return;
  const c = r.querySelector(".mcard.live") || r.querySelector(".mcard.pre"); if (c) r.scrollLeft = c.offsetLeft - r.offsetLeft - 16;
}
