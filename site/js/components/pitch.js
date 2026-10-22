// PlayerCard and PitchView.
/* ---------- pitch ---------- */
function card(id, g, o = {}) {
  const p = P[id]; if (!p) return "";
  const role = o.cap === id ? "captain" : o.vice === id ? "vice-captain" : "";
  const badge = role === "captain" ? `<span class="badge" aria-hidden="true">C</span>` : role ? `<span class="badge v" aria-hidden="true">V</span>` : "";
  const cls = ["pc", o.sel === id ? "sel" : "", o.fresh?.has(id) ? "newin" : ""].join(" ");
  const label = `${p.name}, ${T[p.team].name}, ${money(p.price)}, form ${f1(p.form)}, ${f1(xpg(id, g))} projected points${role ? `, ${role}` : ""}${o.fresh?.has(id) ? ", new signing in your plan" : ""}${p.status !== "a" ? `, ${p.news || "flagged"}` : ""}`;
  return `<button class="${cls}" data-${o.act || "p"}="${id}" aria-label="${esc(label)}">${flag(p)}${badge}
    <img class="shirt" src="${shirtURL(p)}" srcset="${shirtSet(p)}" sizes="30px" alt="" loading="lazy" onerror="this.remove()">
    <span class="nm">${esc(p.name)}</span>
    <span class="xp">${f1(xpg(id, g))}</span>
    <span class="pc-meta"><span>£${p.price.toFixed(1)}m</span><span class="pc-form" title="Form">${f1(p.form)}</span></span>
    <span class="fx">${fxChips(p, g, 3)}</span></button>`;
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
  return `<div class="pitchwrap"><div class="pitch" role="group" aria-label="Starting XI">${rows}</div><div class="bench" role="group" aria-label="Bench"><span class="lbl">Bench</span>${bench.map(i => card(i, g, o)).join("")}</div>
    <div class="pitch-key"><span>Big number: projected points</span><span>Then price and <span class="pc-form">form</span></span>${fdrKey()}</div></div>`;
}
