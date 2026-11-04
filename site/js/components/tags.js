// Player tags: a quick read of form, fixtures, minutes, value and risks, shown next to names.
const TAGS = { key: "", value: new Set() };
function valueSet() {   // the best projected points per £m at each position (top 10%, regular starters only)
  if (TAGS.key === D.meta.built) return TAGS.value;
  const s = new Set();
  ["GKP", "DEF", "MID", "FWD"].forEach(pos => {
    const ps = D.players.filter(p => p.pos === pos && p.nailed >= 70 && p.ok !== false && p.xp5 > 0).sort((a, b) => b.xp5 / b.price - a.xp5 / a.price);
    ps.slice(0, Math.max(2, Math.ceil(ps.length * 0.1))).forEach(p => s.add(p.id));
  });
  TAGS.key = D.meta.built; TAGS.value = s; return s;
}
function banLimit() { const g = D.meta.next_gw || 1; return g <= 19 ? 5 : g <= 32 ? 10 : null; }
function playerTagList(p) {
  const out = [], g = D.meta.next_gw;
  if (p.mins4 >= 180 && p.pos !== "GKP" && p.xgi90_4 >= Math.max(0.45, 1.3 * p.xgi90)) out.push(["hot", "Hot", `xGI/90 over the last 4 (${p.xgi90_4.toFixed(2)}) is well above his usual ${p.xgi90.toFixed(2)}`]);
  else if (p.mins4 >= 180 && p.pos !== "GKP" && p.xgi90 >= 0.3 && p.xgi90_4 <= 0.6 * p.xgi90) out.push(["cold", "Cold", `xGI/90 over the last 4 (${p.xgi90_4.toFixed(2)}) is well below his usual ${p.xgi90.toFixed(2)}`]);
  const fd = GWS.slice(0, 4).flatMap(x => fxFor(p.team, x).map(f => f.fdr || 3));
  if (fd.length >= 3) { const a = fd.reduce((s, v) => s + v, 0) / fd.length;
    if (a <= 2.5) out.push(["easy", "Easy run", `Average FPL difficulty ${a.toFixed(1)} over the next 4 gameweeks`]);
    else if (a >= 3.75) out.push(["tough", "Tough run", `Average FPL difficulty ${a.toFixed(1)} over the next 4 gameweeks`]); }
  if (p.status === "a" && p.ok !== false && p.nailed >= 20 && p.nailed < 60) out.push(["rot", "Rotation risk", `Nailed ${p.nailed}: often benched or subbed early`]);
  if (valueSet().has(p.id)) out.push(["value", "Value", `Among the best projected points per £m for a ${p.pos}`]);
  const lim = banLimit();
  if (lim && p.yc === lim - 1) out.push(["ban", "1 yellow from a ban", `${p.yc} yellow cards: one more before GW${lim === 5 ? 19 : 32} means a one-match ban`]);
  const u = p.upos || "";
  if (p.pos === "DEF" && /[MF]/.test(u.replace(/S/g, ""))) out.push(["oop", "Plays further forward", `FPL lists him as a defender; Understat has him playing as ${u.includes("F") ? "a forward" : "a midfielder"} too`]);
  else if (p.pos === "MID" && /F/.test(u)) out.push(["oop", "Plays up front", "FPL lists him as a midfielder; Understat has him playing as a forward too"]);
  return out;
}
// Set-piece duty as one tag, from FPL's own taker order (penalties_order, corners_and_indirect_freekicks_order,
// direct_freekicks_order): Pens / 2nd on pens, Corners, FKs. Only first choice counts for corners and free kicks.
// Missing: FPL gives no order for most players, so no tag; a club with no order set shows no tags at all (FPL fills
// these in through the season), never a guess from past takes.
function spTag(p) {
  const s = p.sp || {}, bits = [], why = [];
  if (s.pen === 1) { bits.push("Pens"); why.push("first-choice penalty taker"); }
  else if (s.pen === 2) { bits.push("2nd on pens"); why.push("second-choice penalty taker"); }
  if (s.cor === 1) { bits.push("Corners"); why.push("takes corners and indirect free kicks"); }
  if (s.fk === 1) { bits.push("FKs"); why.push("takes direct free kicks"); }
  return bits.length ? ["pen", bits.join(" · "), `FPL lists him as ${why.join(", ")}`] : null;
}
// max limits the other tags; the set-piece tag always shows (it's what you scan for while browsing) and comes first
function playerTags(p, max = 3) {
  const sp = spTag(p), t = [...(sp ? [sp] : []), ...playerTagList(p).slice(0, max)];
  return t.length ? `<span class="ptags">${t.map(([k, l, why]) => `<span class="ptag t-${k}" title="${esc(why)}">${l}</span>`).join("")}</span>` : "";
}
