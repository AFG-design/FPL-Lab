// PlayerCard and PitchView.
/* ---------- pitch ---------- */
function card(id, g, o = {}) {
  const p = P[id]; if (!p) return "";
  const badge = o.cap === id ? `<span class="badge">C</span>` : o.vice === id ? `<span class="badge v">V</span>` : "";
  const cls = ["pc", o.sel === id ? "sel" : "", o.fresh?.has(id) ? "newin" : ""].join(" ");
  return `<button class="${cls}" data-${o.act || "p"}="${id}" aria-label="${esc(p.name)}">${flag(p)}${badge}
    <img class="shirt" src="${shirtURL(p)}" srcset="${shirtSet(p)}" sizes="30px" alt="" loading="lazy" onerror="this.remove()">
    <div class="tm">${T[p.team].short} ${p.price.toFixed(1)}</div>
    <div class="nm">${esc(p.name)}</div>
    <div class="xp">${f1(xpg(id, g))}</div>
    <div class="fx">${fxChips(p, g, 3)}</div></button>`;
}
// the same image sources the official FPL app uses this season
const shirtBase = p => {
  const special = D.meta.special_shirts && !(D.meta.special_excl || []).includes(p.code);
  return `https://fantasy.premierleague.com/dist/img/shirts/${special ? "special" : "standard"}/shirt_${p.tcode}${p.pos === "GKP" ? "_1" : ""}`;
};
const shirtURL = p => `${shirtBase(p)}-110.webp`;
const shirtSet = p => `${shirtBase(p)}-66.webp 66w, ${shirtBase(p)}-110.webp 110w, ${shirtBase(p)}-220.webp 220w`;
const PHOTO_BASE = "https://resources.premierleague.com/premierleague25/photos/players/110x140";
const photoURL = p => `${PHOTO_BASE}/${p.tmp ? "placeholder" : p.code}.png`;
function pitch(xi, bench, g, o = {}) {
  const rows = ["GKP", "DEF", "MID", "FWD"].map(pos => `<div class="row">${xi.filter(i => P[i]?.pos === pos).map(i => card(i, g, o)).join("")}</div>`).join("");
  return `<div class="pitchwrap"><div class="pitch">${rows}</div><div class="bench"><span class="lbl">Bench</span>${bench.map(i => card(i, g, o)).join("")}</div></div>`;
}
