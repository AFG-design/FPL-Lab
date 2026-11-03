// PlayerCard and PitchView: one lineup component for Home (Next deadline, Current GW) and the Planner.
// Two styles share the same markup, data and actions; only CSS differs:
//   Cards  compact cards: kit beside the name, the big number on the right, the next fixture underneath
//   Kits   a kit above a small dark nameplate, so more of the pitch shows
// The style is a display preference (S.lineup, localStorage "fpl.lineup"): Cards when nothing is saved or storage is
// unavailable. Switching re-draws the same lineup, so the squad, captain, bench order, gameweek and plan don't change.
// Price, form and longer fixture runs live in the player panel (tap a player), not on the card.
// Fixtures are FPL's difficulty chips (number printed, capitals = home), one per match: a double gameweek shows two, a
// blank shows "No match". The Planner adds a three-week run (o.run) and, in Your plan, each player's price (o.price:
// your real selling price for players you own, the buying price for planned signings). The captain's projected
// number shows "×2" beside it; Current GW's actual points already include the armband and are never marked again.
// Missing or ambiguous data: no difficulty from FPL -> the chip says 3 (fdrChip's default, as everywhere else); an id
// missing from the data isn't drawn; projections resting on assumptions keep their dotted "assumed" mark.
S.lineup = store.get("fpl.lineup") === "kits" ? "kits" : "cards";
function lineupToggle() {
  return `<div class="seg lu-toggle" role="group" aria-label="Lineup style">${[["cards", "Cards"], ["kits", "Kits"]].map(([k, l]) =>
    `<button type="button" data-lineup="${k}" aria-pressed="${S.lineup === k}">${l}</button>`).join("")}</div>`;
}
// the gameweek's fixtures as short text, every fixture of a double gameweek included
function fxShort(p, g) {
  const fx = fxFor(p.team, g);
  if (!fx.length) return { txt: "No match", lbl: `no match in GW${g}` };
  return { txt: fx.map(x => `${T[x.opp].short}${fx.length > 1 ? "" : " "}(${x.home ? "H" : "A"})`).join("+"),
    lbl: `${fx.length > 1 ? `${fx.length} matches in GW${g}: ` : ""}${fx.map(x => `${T[x.opp].name} ${x.home ? "at home" : "away"}`).join(" and ")}` };
}
// one card. o: { id, big (the number, HTML), bigCls, sub (text under the name) or subHtml, ex (an extra line, HTML),
// role ("cap" | "vice" | "capvice"), act (data attribute, default "p"), sel, fresh, cls, label, bench (its bench slot) }
function luCard(o) {
  const p = P[o.id]; if (!p) return "";
  const role = o.role === "cap" || o.role === "capvice" ? '<span class="lu-role" aria-hidden="true">C</span>' : o.role === "vice" ? '<span class="lu-role v" aria-hidden="true">V</span>' : "";
  // long names get a slightly smaller face where cards are narrow, instead of breaking mid-word
  const cls = ["pc", "lu-pc", o.sel ? "sel" : "", o.fresh ? "newin" : "", p.name.length >= 10 ? "lu-long" : "", o.cls || ""].join(" ").trim();
  return `<button type="button" class="${cls}" data-${o.act || "p"}="${o.id}" style="--club:${clubCol(p)}" aria-label="${esc(o.label)}">
    <span class="lu-box">${o.bench ? `<span class="lu-slot" aria-hidden="true">${o.bench}</span>` : ""}
    <span class="lu-kit">${flag(p)}<img class="shirt" src="${shirtURL(p)}" srcset="${shirtSet(p)}" sizes="30px" alt="" loading="lazy" onerror="this.remove()">${role}</span>
    <span class="lu-txt"><span class="nm">${esc(p.name)}${o.fresh ? '<span class="lu-in" aria-hidden="true">IN</span>' : ""}</span>
      <span class="lu-line"><span class="xp${o.bigCls ? " " + o.bigCls : ""}">${o.big}</span><span class="lu-sub">${o.subHtml ?? esc(o.sub)}</span></span>${o.ex ? `<span class="lu-ex">${o.ex}</span>` : ""}</span></span></button>`;
}
// bench slots in FPL's order: the keeper, then outfield subs 1, 2, 3
const benchSlots = ids => { let n = 0; return ids.map(i => P[i]?.pos === "GKP" ? "GK" : String(++n)); };
function luPitch(xi, bench, { key = "", note = "", label = "Starting XI" } = {}) {
  const lines = ["GKP", "DEF", "MID", "FWD"].map(pos => xi.filter(x => P[x.id]?.pos === pos));
  const rows = lines.map(l => `<div class="row">${l.map(luCard).join("")}</div>`).join("");
  const slots = benchSlots(bench.map(x => x.id));
  // the busiest row decides when the whole lineup switches to the stacked card layout, so one lineup never mixes them
  const most = Math.min(5, Math.max(3, ...lines.map(l => l.length)));
  return `<div class="pitchwrap lu lu-${S.lineup} lu-r${most}"><div class="pitch" role="group" aria-label="${label}">${rows}</div>
    <div class="bench lu-bench" role="group" aria-label="Bench, in substitution order"><span class="lbl">Bench</span>${bench.map((x, k) => luCard({ ...x, bench: slots[k], cls: (x.cls || "") + " lu-bn" })).join("")}</div>
    ${note ? `<p class="bench-note">${note}</p>` : ""}<div class="pitch-key">${key}</div></div>`;
}

/* ---------- projected points (Next deadline, Planner) ---------- */
// this gameweek's fixtures as difficulty chips: one per match, "No match" for a blank
function fxChipsGw(p, g) {
  const fx = fxFor(p.team, g);
  return fx.length ? fx.map(x => fdrChip(x, { gw: g, size: "xs" })).join("") : '<span class="fdr blank xs">No match</span>';
}
// the following n gameweeks as small dots coloured by difficulty: split for a double, hollow for a blank
function runDots(p, g, n) {
  const gws = GWS.filter(x => x > g).slice(0, n);
  if (!gws.length) return { html: "", lbl: "" };
  const dot = gw => {
    const fx = fxFor(p.team, gw);
    if (!fx.length) return '<i class="lu-dot blank"></i>';
    return `<i class="lu-dot${fx.length > 1 ? " dbl" : ""}">${fx.map(x => `<b class="d${Math.min(5, Math.max(1, x.fdr || 3))}"></b>`).join("")}</i>`;
  };
  const lbl = gws.map(gw => { const fx = fxFor(p.team, gw); return fx.length ? fx.map(x => `${T[x.opp].short} ${x.home ? "home" : "away"} (${Math.min(5, Math.max(1, x.fdr || 3))})`).join(" and ") : "no match"; }).join(", ");
  return { html: `<span class="lu-run" aria-hidden="true" title="Next ${gws.length}: ${esc(lbl)}">${gws.map(dot).join("")}</span>`, lbl: `next ${gws.length}: ${lbl}` };
}
function projItem(id, g, o) {
  const p = P[id]; if (!p) return null;
  const role = o.cap === id ? "cap" : o.vice === id ? "vice" : "";
  const fx = fxShort(p, g), fresh = !!o.fresh?.has(id), asm = isAsm(id, g), x = xpg(id, g);
  const run = o.run ? runDots(p, g, o.run) : null;
  const owned = D.squad.some(s => s.id === id);
  const price = o.price ? (owned ? { txt: `sells ${money(sellPrice(id))}`, lbl: `selling price ${money(sellPrice(id))}` } : { txt: money(p.price), lbl: `costs ${money(p.price)}` }) : null;
  const ex = run || price ? `${run ? run.html : ""}${price ? `<span class="lu-price">${price.txt}</span>` : ""}` : "";
  const label = `${p.name}, ${T[p.team].name}, ${f1(x)} projected points in GW${g}${role === "cap" ? `, captain: ${f1(2 * x)} with the armband` : role === "vice" ? ", vice-captain" : ""}${asm ? " (assumed, no official data)" : ""}, ${fx.lbl}${run?.lbl ? `, ${run.lbl}` : ""}${price ? `, ${price.lbl}` : ""}${fresh ? ", new signing in your plan" : ""}${p.status !== "a" ? `, ${p.news || "flagged"}${p.chance != null ? `, ${p.chance}% chance of playing` : ""}` : ""}. Opens player details`;
  return { id, big: `${f1(x)}${role === "cap" ? '<small class="lu-x">×2</small>' : ""}`, bigCls: asm ? "asm" : "", subHtml: fxChipsGw(p, g), ex, role, act: o.act, sel: o.sel === id, fresh, label };
}
function pitch(xi, bench, g, o = {}) {
  const it = id => projItem(id, g, o);
  return luPitch(xi.map(it).filter(Boolean), bench.map(it).filter(Boolean), {
    key: `<span>Big number: projected points for GW${g}; the captain's ×2 is marked, not added</span><span>C captain · V vice · % chance of playing · IN new signing</span>${o.run ? `<span>Dots: the next ${o.run} gameweeks' difficulty (split = double, hollow = blank)</span>` : ""}${o.price ? "<span>Price: your selling price for players you own, the buying price for signings</span>" : ""}${fdrKey()}`,
  });
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

/* ---------- actual points (Current GW) ---------- */
// x: { r (live row), st (match state), played, pts (what counts, armband applied), mult, counts, role, note }.
// The number already includes the armband (FPL's convention for actual points), so it is never doubled again; the
// card says "C ×2" and the key says so too. "–" for a player whose matches haven't started.
function liveItem(x) {
  const p = P[x.r.id]; if (!p) return null;
  const big = x.st.key === "toplay" && !x.played ? "–" : String(x.pts);
  const sub = x.note || (x.mult > 1 ? `${x.st.label} · C ×${x.mult}` : x.st.label);
  const role = x.role === "capvice" ? "capvice" : x.role;
  const label = `${p.name}, ${T[p.team].name}, ${x.st.label}${big === "–" ? "" : `, ${x.pts} actual point${x.pts === 1 ? "" : "s"}${x.mult > 1 ? ` including the ×${x.mult} armband` : ""}`}${x.counts === false ? ", not counted (bench)" : ""}${x.note ? ", " + x.note : ""}${role === "cap" ? ", captain" : role === "capvice" ? ", vice-captain wearing the armband" : role === "vice" ? ", vice-captain" : ""}${p.status !== "a" ? `, ${p.news || "flagged"}` : ""}. Opens player details`;
  return { id: x.r.id, big, sub, role, label, cls: `lvc lvc-${x.st.key}${x.counts === false ? " lvc-nocount" : ""}` };
}
function livePitch(xi, bench, benchNote, key) {
  return luPitch(xi.map(liveItem).filter(Boolean), bench.map(liveItem).filter(Boolean), { key, note: benchNote, label: "Starting XI as submitted" });
}
