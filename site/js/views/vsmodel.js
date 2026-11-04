// You vs the model (F1d): each finished gameweek, your actual points against the model's target, with both teams on
// pitches side by side. The data comes from build.py's vs_model block (fpl_score.py has the rules).
//   Result: your actual points after hits v the model's target = its highest projected score for that week across
//   every plan it suggested before the deadline (xP less 4 per hit), rounded to the nearest point. Above: win.
//   Your pitch: the XI you submitted with each player's actual points (armband included), auto-subs marked.
//   The model's pitch: the XI of its best suggested plan with each player's projected points from before the deadline
//   and, under it, what he actually scored. Players it signed show IN; the moves and hits are listed below the pitch.
// Missing / late / ambiguous:
//   - no vs_model in the data (no saved forecast yet, or the build step failed): an empty state, nothing made up;
//   - a week with no saved suggestion (GW8 and GW9: saving began at GW10): target.assumed; the model's side is then its
//     best pick from your own 15 (no transfers) and the page says so above the pitches;
//   - the suggested plan's bench wasn't saved, so its pitch has no bench and says so;
//   - the gameweek to come: its target is the best suggestion so far, which can change with each refresh until the
//     deadline (the page says so); no saved plans yet -> "no target yet";
//   - a player no longer in the data isn't drawn (luCard skips him).
const VM_MODE = { safe: "Safe", chase: "Chase" };
// "chase_two" -> "Chase · 2 moves"; a key with no mode prefix is the Balanced plan
function vmPlan(key) {
  const [m, v] = key.includes("_") ? key.split("_") : ["", key];
  return `${VM_MODE[m] || "Balanced"} · ${PLAN_LABEL[v] || v}`;
}
const vmRes = { W: ["Win", "good"], D: ["Draw", "warn"], L: ["Defeat", "bad"] };
const vmNm = i => P[i] ? esc(P[i].name) : "Unknown player";
const vmPts = n => `${n} pt${n === 1 ? "" : "s"}`;

// your side: the XI as submitted, actual points; who was subbed off or on, and whose points counted
function vmYouItems(w) {
  const y = w.you, subs = y.subs || [], bb = w.chip === "bboost";
  const offs = new Set(subs.map(s => s[0])), ons = new Set(subs.map(s => s[1]));
  const mult = w.chip === "3xc" ? 3 : 2;
  const item = (id, onBench) => {
    const p = P[id]; if (!p) return null;
    const raw = w.pts[id] ?? 0, m = id === y.armband ? mult : 1, counts = bb || (onBench ? ons.has(id) : !offs.has(id));
    const role = id === y.cap ? "cap" : id === y.vice ? (y.armband === id ? "capvice" : "vice") : "";
    const note = offs.has(id) ? "Subbed off (0 mins)" : ons.has(id) ? "Came on" : onBench && !counts ? "Not counted" : "";
    const big = String(counts ? raw * m : raw);
    const label = `${p.name}, ${raw} actual point${raw === 1 ? "" : "s"}${m > 1 && counts ? `, ×${m} with the armband` : ""}${note ? ", " + note : ""}. Opens player details`;
    const foot = [note && esc(note), m > 1 && counts ? `Armband ×${m} included` : ""].filter(Boolean);
    return { id, big, sub: note || "Actual", role, label, cls: counts ? "" : "lvc-nocount",
      c: { unit: big === "1" ? "pt" : "pts", x2: m > 1 && counts ? `C ×${m}` : "", sub: "Actual", foot } };
  };
  return { xi: y.xi.map(i => item(i, false)).filter(Boolean), bench: y.bench.map(i => item(i, true)).filter(Boolean) };
}

// the model's side: projected points before the deadline (the big number) and what each player actually scored
function vmModelItems(t, xpOf, ptsOf, squad, done, chip) {
  const mult = chip === "3xc" ? 3 : 2;
  const item = (id, onBench) => {
    const p = P[id]; if (!p) return null;
    const xp = xpOf(id), cap = id === t.cap, m = cap && !onBench ? mult : 1, fresh = !squad.has(id);
    const act = ptsOf(id);
    const sub = done && act != null ? `Scored ${act}` : "Projected";
    const label = `${p.name}, ${f1(xp)} projected point${xp === 1 ? "" : "s"} before the deadline${m > 1 ? `, ×${m} as captain` : ""}${done && act != null ? `, scored ${act}` : ""}${fresh ? ", signed by the model" : ""}${cap ? ", captain" : id === t.vice ? ", vice-captain" : ""}. Opens player details`;
    return { id, big: f1(xp * m), sub, role: cap ? "cap" : id === t.vice ? "vice" : "", fresh, label,
      c: { unit: "xP", x2: m > 1 ? `C ×${m}` : "", sub, foot: [] } };
  };
  return { xi: t.xi.map(i => item(i, false)).filter(Boolean), bench: (t.bench || []).map(i => item(i, true)).filter(Boolean) };
}

const vmMoves = t => t.out?.length
  ? `<ul class="vm-moves">${t.out.map((o, k) => `<li><span class="out">▼ ${vmNm(o)}</span> <span class="in">▲ <button type="button" class="linkish" data-p="${t.in[k]}">${vmNm(t.in[k])}</button></span></li>`).join("")}</ul>
     <p class="note">${t.hits ? `${t.hits} hit${t.hits > 1 ? "s" : ""}: −${t.hits * 4} taken off its projection` : "No hits"}</p>`
  : `<p class="note">No transfers: it kept the 15 you had.</p>`;

function vmScore(you, youSub, par, parSub, res) {
  const [word, tone] = res ? vmRes[res] : ["To play", "mut"];
  return `<div class="vm-score" role="group" aria-label="Score">
    <div class="vm-side"><span class="lbl">You</span><b>${you ?? "–"}</b><span class="note">${youSub}</span></div>
    <span class="pill ${tone} vm-res">${word}</span>
    <div class="vm-side"><span class="lbl">Model's target</span><b>${par ?? "–"}</b><span class="note">${parSub}</span></div></div>`;
}

function vmWeek(w) {
  const t = w.target, squad = new Set(Object.keys(w.xp).map(Number));
  const youP = vmYouItems(w);
  const sug = t.basis === "suggested";
  const mt = sug ? { xi: t.xi, bench: [], cap: t.captain, vice: null, out: t.out, in: t.in, hits: t.hits }
    : { xi: w.model.xi, bench: w.model.bench, cap: w.model.cap, vice: w.model.vice, out: [], in: [], hits: 0 };
  const xpOf = sug ? i => t.xi_xp?.[i] ?? 0 : i => w.xp[i] ?? 0;
  const ptsOf = sug ? i => t.xi_pts?.[i] : i => w.pts[i];
  const modP = vmModelItems(mt, xpOf, ptsOf, squad, true, w.chip);
  const modelActual = sug ? t.actual : w.model.pts;
  const hitsTxt = w.hits ? `after −${w.hits} in hits` : "no hits";
  return `<div class="panel vm-head"><h2>GW${w.gw}: you v the model</h2>
      ${vmScore(w.you_net, `Actual points, ${hitsTxt}`, t.par, `Its best projected score before the deadline: ${f1(t.exp)}, rounded`, w.res)}
      ${t.assumed ? `<p class="vm-assumed"><b>Assumed target.</b> No suggestion was saved before the GW${w.gw} deadline (saving began at GW10), so the target is what the model projected for its best pick from your own 15, with no transfers.</p>` : ""}
      ${w.you.pts !== w.fpl_pts ? `<p class="vm-assumed"><b>Check:</b> our rules give your team ${w.you.pts}, FPL gave ${w.fpl_pts}.</p>` : ""}
    </div>
    <div class="grid2 vm-cols">
      <div class="panel"><div class="bar"><h3>Your team</h3><span class="tag">Actual points</span></div>
        ${luPitch(youP.xi, youP.bench, { label: `Your GW${w.gw} XI as submitted`, note: w.you.subs?.length ? `Auto-subs: ${w.you.subs.map(([o, i]) => `${vmNm(o)} → ${vmNm(i)}`).join(", ")}` : "No auto-subs" })}
        <p class="note">${w.you.formation} · ${w.you.pts} points before hits${w.chip ? ` · chip: ${esc(w.chip)}` : ""}</p></div>
      <div class="panel"><div class="bar"><h3>The model</h3><span class="tag">${sug ? esc(vmPlan(t.plan)) : "Best pick from your 15"}</span></div>
        ${luPitch(modP.xi, modP.bench, { label: `The model's GW${w.gw} XI`, note: sug ? "Its bench wasn't saved with the plan." : "" })}
        ${sug ? vmMoves(mt) : ""}
        <p class="note">Big number: projected points before the deadline (captain ×2 included). "Scored": what he actually got. Its XI actually scored <b>${modelActual}</b>${sug ? " (no auto-subs, after hits)" : ""}, shown for interest: the result uses its projection.</p></div>
    </div>`;
}

function vmNext(n) {
  const t = n.target;
  if (!t) return `<div class="panel"><h2>GW${n.gw}: the score to beat</h2><p>No target yet: it appears once the model's plans for GW${n.gw} are saved on the next refresh.</p></div>`;
  const items = vmModelItems({ xi: t.xi, bench: [], cap: t.captain }, i => xpg(i, n.gw), () => null, new Set(D.squad.map(s => s.id)), false, null);
  return `<div class="panel vm-head"><h2>GW${n.gw}: the score to beat</h2>
      ${vmScore(null, "Your actual points, after hits, once GW" + n.gw + " finishes", t.par, `Its best projected score so far: ${f1(t.exp)}, rounded`, null)}
      <p class="note">The target is fixed at the deadline${n.deadline ? ` (${esc(ukTime(n.deadline))})` : ""}. Until then it follows the model's latest plans and can change with each refresh.</p></div>
    <div class="panel" style="max-width:720px"><div class="bar"><h3>What the model suggests</h3><span class="tag">${esc(vmPlan(t.plan))}</span></div>
      ${luPitch(items.xi, [], { label: `The model's GW${n.gw} XI`, note: "Its bench isn't saved with the plan." })}
      ${vmMoves(t)}
      <p class="note">Big number: projected points for GW${n.gw} (captain ×2 included).</p></div>`;
}

function vVsModel() {
  const V = D.vs_model;
  if (!V || !V.weeks?.length) return stateView({ kind: "empty", title: "You vs the model isn't ready", body: "It needs a finished gameweek with a forecast saved before its deadline. It appears after the next data refresh." });
  const weeks = V.weeks.slice().reverse(), n = V.next;
  const opts = [...(n?.gw ? [[`n${n.gw}`, `GW${n.gw}`]] : []), ...weeks.map(w => [String(w.gw), `GW${w.gw}`])];
  if (!opts.some(([k]) => k === S.vmgw)) S.vmgw = String(weeks[0].gw);
  const w = weeks.find(x => String(x.gw) === S.vmgw);
  return `<div class="panel vm-intro"><h2>You vs the model</h2>
      <p>Each gameweek your actual points, after hits, against the model's target: its highest projected score for that week from what it suggested before the deadline, rounded. Beat it to win the week.</p>
      <div class="seg vm-gws" role="group" aria-label="Gameweek">${opts.map(([k, l]) => `<button type="button" data-vmgw="${k}" aria-pressed="${k === S.vmgw}">${l}${k[0] === "n" ? " · to play" : ` · ${vmRes[V.weeks.find(x => String(x.gw) === k).res][0]}`}</button>`).join("")}</div>
      ${lineupToggle()}</div>
    ${w ? vmWeek(w) : vmNext(n)}`;
}
