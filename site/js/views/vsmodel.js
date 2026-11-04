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

// gw: given only for the week to come, where each suggestion gets a "Why not?" (D5b)
const vmMoves = (t, gw) => t.out?.length
  ? `<ul class="vm-moves">${t.out.map((o, k) => `<li><span class="out">▼ ${vmNm(o)}</span> <span class="in">▲ <button type="button" class="linkish" data-p="${t.in[k]}">${vmNm(t.in[k])}</button></span>${gw ? reasonBtn(gw, o, t.in[k], "whynot") : ""}</li>`).join("")}</ul>
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
      ${vmMoves(t, n.gw)}
      <p class="note">Not making one of these? Tap Why not? to note your reason; it goes in the decision journal.</p>
      <p class="note">Big number: projected points for GW${n.gw} (captain ×2 included).</p></div>`;
}

// Decision journal (D5a): your moves and captain next to the model's suggestion for the same week, with what the app
// knew about each player before the deadline (build.py's journal block, decision_journal.py). Shown per gameweek.
// Missing / ambiguous: no entry for a finished week (no deadline snapshot: GW8, GW9) -> says why; the week to come ->
// says when its entry is saved; a player missing from the snapshot -> "not in the forecast", never a made-up 0; start
// chance unknown -> "–"; Free Hit -> the moves were for one week only, and the page says so.
const jPct = x => x == null ? "–" : Math.round(x * 100) + "%";
function jFx(r) { return r.fx?.length ? r.fx.map(([o, h]) => `${esc(T[o]?.short || "?")} (${h ? "H" : "A"})`).join(" + ") : "No match"; }
function jFlag(r) { return r.status && r.status !== "a" ? ` <span class="tag warn" title="FPL flag before the deadline">${r.chance != null ? r.chance + "%" : esc(r.status)}</span>` : ""; }
// how a move turned out so far (D5c): both players' own points over the finished weeks of its window, next to what
// was projected for the same weeks, and the deadline week's assumptions check
const jGws = gs => gs.length > 1 ? `GW${gs[0]}–${gs[gs.length - 1]}` : `GW${gs[0]}`;
function jCheck(id, c) {
  if (!c) return "";
  const exp = [c.xmin != null ? `expected ${c.xmin}` : "", c.start_chance != null ? `${jPct(c.start_chance)} to start` : ""].filter(Boolean).join(", ");
  return `${vmNm(id)} ${c.started ? "started" : c.mins ? "came off the bench" : "didn't play"}, ${c.mins} min${exp ? ` (${exp})` : ""}`;
}
function jResult(o, i, e) {
  const oc = e.outcome, m = oc?.moves?.[`${o}-${i}`];
  if (!m) return "";
  const full = oc.gws.length === oc.of;
  return `<div class="j-res"><span><b>${full ? "Result" : "So far"}</b> · ${jGws(oc.gws)} (${oc.gws.length} of ${oc.of}): ${vmNm(i)} ${m.in_pts} v ${vmNm(o)} ${m.out_pts} <b class="${m.gain > 0 ? "up" : m.gain < 0 ? "down" : ""}">${m.gain > 0 ? "+" : m.gain < 0 ? "−" : "±"}${Math.abs(m.gain)}</b> <span class="muted">· projected ${sgn(m.proj_gain)} for those weeks</span></span>
    ${m.check.in || m.check.out ? `<span class="muted">GW${e.gw}: ${[jCheck(i, m.check.in), jCheck(o, m.check.out)].filter(Boolean).join(" · ")}</span>` : ""}</div>`;
}
function jRow([o, i], e, kind) {
  const po = e.players[o] || {}, pi = e.players[i] || {};
  const d = (pi.xp5 || 0) - (po.xp5 || 0);
  const side = (id, r) => `<button type="button" class="linkish" data-p="${id}">${vmNm(id)}</button>${jFlag(r)}${r.absent ? ' <span class="muted">(not in the forecast)</span>' : ""}`;
  return `<li class="j-row"><div class="j-move"><span class="out">▼ ${side(o, po)}</span><span class="in">▲ ${side(i, pi)}</span></div>
    <div class="j-facts"><span>xP next 5: ${f1(po.xp5)} → <b>${f1(pi.xp5)}</b> <b class="${d >= 0 ? "up" : "down"}">${sgn(d)}</b></span>
      <span>Start chance: ${jPct(po.start)} → ${jPct(pi.start)}</span><span>GW${e.gw}: ${jFx(pi)}</span></div>
    ${jResult(o, i, e)}<div class="j-why">${reasonBtn(e.gw, o, i, kind)}</div></li>`;
}
function journalPanel(gw, isNext) {
  const J = D.journal, e = J?.weeks?.find(x => x.gw === gw);
  const head = `<div class="bar"><h3>Decision journal · GW${gw}</h3><span class="tag">Saved before the deadline</span></div>`;
  if (!J) return `<div class="panel j-panel">${head}<p class="note">The journal isn't in this data update. It comes back on the next refresh.</p></div>`;
  if (!e) {
    const why = isNext ? `GW${gw}'s entry is saved when the deadline passes${D.vs_model?.next?.deadline ? ` (${esc(ukTime(D.vs_model.next.deadline))})` : ""}: your transfers and captain next to the model's suggestion, with what it knew about each player.`
      : J.no_snapshot?.includes(gw) ? `No entry for GW${gw}: the model's suggestions weren't saved before that deadline (saving began at GW10).`
      : J.skipped?.includes(gw) ? `No entry for GW${gw}: your picks couldn't be fetched this update.` : `No entry for GW${gw}.`;
    return `<div class="panel j-panel">${head}<p class="note">${why}</p></div>`;
  }
  const r = id => e.players[id] || {};
  const grp = (title, list, empty, kind) => `<div class="j-grp"><h4>${title} <span class="muted">${list.length}</span></h4>${list.length ? `<ul>${list.map(m => jRow(m, e, kind)).join("")}</ul>` : `<p class="note">${empty}</p>`}</div>`;
  const yc = e.you.captain, mc = e.model?.captain, oc = e.outcome, cp = oc?.captain;
  return `<div class="panel j-panel">${head}
    ${e.chip === "freehit" ? '<p class="vm-assumed"><b>Free Hit:</b> these moves were for this week only.</p>' : ""}
    <div class="j-cap"><span>Captain</span><span>You: <b>${vmNm(yc)}</b> ${f1(r(yc).xp1)} xP</span>${e.model ? `<span>Model: <b>${vmNm(mc)}</b> ${f1(r(mc).xp1)} xP${mc === yc ? ' <span class="pill good">Same</span>' : ""}</span>` : ""}${cp ? `<span class="j-capres">Scored: you ${cp.you_pts}${e.model && cp.model_pts != null && mc !== yc ? `, model ${cp.model_pts}` : ""} <span class="muted">(before the armband)</span></span>` : ""}</div>
    ${e.model ? `<p class="note">The model's suggestion: ${esc(vmPlan(e.model.plan))}${e.model.hits ? `, ${e.model.hits} hit${e.model.hits > 1 ? "s" : ""}` : ", no hits"}. Your hits: ${e.hits ? "−" + e.hits : "none"}.</p>` : '<p class="note">No saved plan for this week, so there is nothing to compare your moves with.</p>'}
    ${grp("You and the model", e.both, "No move in common.", "why")}
    ${grp("Your calls", e.yours, "None: every move you made was one it suggested.", "why")}
    ${e.model ? grp("Its suggestions you skipped", e.skipped, "None: you made every move it suggested.", "whynot") : ""}
    <p class="note">xP next 5: projected points over the five gameweeks from GW${gw}, as saved before the deadline. Start chance and flags as they stood then. ${oc ? `Results: each player's own points over ${e.chip === "freehit" ? `GW${gw} (Free Hit)` : `GW${gw}–${gw + 4}`} as they're played, whether or not you started him.` : `Results appear here once GW${gw} has been played, and build up over the five weeks.`}</p></div>`;
}

// Season summary of the journal (D5d), worked out in the page from the journal's results (data) and your reasons
// (this browser / plan sync). "+" always means the call paid off for you:
//   - a move you made (both, or your own call): his points minus the player you sold, over the weeks played so far;
//   - a suggestion you skipped: minus what it would have gained (it lost points -> skipping it was right -> +).
// Missing / ambiguous: no results yet -> says when the summary starts; a move with no result yet (its first week not
// played) isn't counted; reasons only on this device when sync is off (the dialog already says so); a move tagged with
// two reasons counts under both, so the reason rows can add up to more than the total, and the page says so.
function jSummary() {
  const W = (D.journal?.weeks || []).filter(e => e.outcome);
  if (!W.length) return `<div class="panel j-sum"><h3>Journal: season so far</h3><p class="note">The summary starts once your first journal week (GW10) has been played: how your own calls, the model's suggestions you skipped and each reason have paid off.</p></div>`;
  const g = { both: { n: 0, net: 0, proj: 0 }, yours: { n: 0, net: 0, proj: 0 }, skipped: { n: 0, net: 0, proj: 0 } };
  const tags = {}, miss = { hi: 0, hiN: 0, lo: 0, loN: 0, minErr: 0, minN: 0 };
  let partial = false;
  W.forEach(e => {
    const oc = e.outcome; if (oc.gws.length < oc.of) partial = true;
    [["both", "why", 1], ["yours", "why", 1], ["skipped", "whynot", -1]].forEach(([grp, kind, sign]) => (e[grp] || []).forEach(([o, i]) => {
      const m = oc.moves[`${o}-${i}`]; if (!m) return;
      g[grp].n++; g[grp].net += m.gain; g[grp].proj += m.proj_gain;
      const r = reasonOf(e.gw, o, i);
      (r?.tags || []).forEach(t => { const k = `${kind}:${t}`; tags[k] = tags[k] || { kind, t, n: 0, net: 0 }; tags[k].n++; tags[k].net += sign * m.gain; });
      [m.check.in, m.check.out].forEach(c => {
        if (!c || c.start_chance == null) return;
        if (c.start_chance >= 0.75) { miss.hiN++; if (!c.started) miss.hi++; }
        if (c.start_chance < 0.5) { miss.loN++; if (c.started) miss.lo++; }
        if (c.xmin != null) { miss.minN++; miss.minErr += c.mins - c.xmin; }
      });
    }));
  });
  const pts = x => { const r = Math.round(x); return `${r > 0 ? "+" : r < 0 ? "−" : "±"}${Math.abs(r)}`; };
  const row = (label, o, sign, note) => `<tr><th scope="row">${label}<small class="muted">${note}</small></th><td class="n">${o.n}</td><td class="n"><b class="${sign * o.net > 0 ? "up" : sign * o.net < 0 ? "down" : ""}">${pts(sign * o.net)}</b></td><td class="n muted">${pts(sign * o.proj)}</td></tr>`;
  const tagRows = Object.values(tags).sort((a, b) => b.net - a.net).map(x => `<tr><th scope="row">${x.kind === "why" ? "Why" : "Why not"}: ${esc(REASON_WORD[x.t])}</th><td class="n">${x.n}</td><td class="n"><b class="${x.net > 0 ? "up" : x.net < 0 ? "down" : ""}">${pts(x.net)}</b></td></tr>`).join("");
  const over = g.yours.net - g.skipped.net;
  const missLines = [
    miss.hiN ? `${miss.hi} of ${miss.hiN} players it gave a 75%+ start chance didn't start` : "",
    miss.loN ? `${miss.lo} of ${miss.loN} it gave under 50% did start` : "",
    miss.minN ? `minutes: ${miss.minErr / miss.minN >= 0 ? "+" : "−"}${Math.abs(Math.round(miss.minErr / miss.minN))} a player on average against expected` : "",
    g.skipped.n + g.both.n ? `its moves gained ${pts(g.skipped.net + g.both.net)} against ${pts(g.skipped.proj + g.both.proj)} projected` : ""].filter(Boolean);
  return `<div class="panel j-sum"><div class="bar"><h3>Journal: season so far</h3><span class="tag">${W.length} week${W.length === 1 ? "" : "s"}${partial ? " · some still being played" : ""}</span></div>
    <p class="vm-sumline"><b>Your calls v the model's:</b> your own moves gained <b class="${g.yours.net >= 0 ? "up" : "down"}">${pts(g.yours.net)}</b>; the suggestions you skipped would have gained ${pts(g.skipped.net)}. Overriding the model: <b class="${over > 0 ? "up" : over < 0 ? "down" : ""}">${pts(over)}</b> to you.</p>
    <div class="tablebox"><table class="j-tbl"><caption class="sr">Moves by group</caption><thead><tr><th scope="col"></th><th scope="col" class="n">Moves</th><th scope="col" class="n">For you</th><th scope="col" class="n"><abbr title="Projected before the deadline for the same weeks">Proj.</abbr></th></tr></thead><tbody>
      ${row("You and the model", g.both, 1, "Moves you both made")}
      ${row("Your calls", g.yours, 1, "Moves it didn't suggest")}
      ${row("Suggestions you skipped", g.skipped, -1, "+ means skipping was right")}
    </tbody></table></div>
    <h4>By reason</h4>
    ${tagRows ? `<div class="tablebox"><table class="j-tbl"><caption class="sr">Points by reason</caption><thead><tr><th scope="col"></th><th scope="col" class="n">Calls</th><th scope="col" class="n">For you</th></tr></thead><tbody>${tagRows}</tbody></table></div><p class="note">A call with two reasons counts under both.</p>`
      : `<p class="note">No reasons tagged on these weeks yet. Add a Why? or Why not? on the journal rows and they're counted here.</p>`}
    <h4>Where the model missed</h4>
    ${missLines.length ? `<ul class="j-miss">${missLines.map(x => `<li>${x}</li>`).join("")}</ul>` : '<p class="note">Nothing to check yet.</p>'}
    <p class="note">Points are each player's own over the weeks played so far of each move's 5-week window, whether or not you started him. "Projected" is what the forecast saved before the deadline expected for the same weeks.</p></div>`;
}

// The streak card (F1e). Everything comes from fpl_score.streak via build.py: run, best, record, wildcards, milestones
// and trail (one entry per week). The page adds nothing of its own except "wins to go", which is n − run.
// Missing / ambiguous: no trail (an older data file) -> circles without the saved / milestone marks, still correct
// W/D/L; a week whose target was assumed gets a dotted circle and the key explains it; next week's "?" circle only
// when the data has a gameweek to come.
const VM_LET = { W: "W", D: "D", L: "L" };
function vmStreak(V) {
  const run = V.run || 0, trail = V.trail || [], held = V.held || 0, n = V.next;
  const head = run ? `${run} win${run === 1 ? "" : "s"} in a row` : "No winning run";
  const sub = run ? `Best run this season: ${V.best}` : `Best run this season: ${V.best || 0}.${n?.gw ? ` Win GW${n.gw} to start a new one.` : ""}`;
  const dots = V.weeks.map((w, k) => {
    const t = trail[k] || {}, word = vmRes[w.res][0];
    const extra = [t.saved ? "a Streak Wildcard saved the run" : "", t.earned ? `${t.earned} reached: Streak Wildcard earned` : "", t.ended ? "run ended" : "", w.target?.assumed ? "assumed target" : ""].filter(Boolean);
    return `<button type="button" class="vm-dot r${w.res}${w.target?.assumed ? " asm" : ""}${t.saved ? " saved" : ""}" data-vmgw="${w.gw}" aria-label="GW${w.gw}: ${word}, ${w.you_net} v ${w.target.par}${extra.length ? ", " + extra.join(", ") : ""}">
      <span class="vm-l" aria-hidden="true">${VM_LET[w.res]}</span><span class="vm-g">GW${w.gw}</span>${t.earned ? '<span class="vm-star" aria-hidden="true">★</span>' : ""}</button>`;
  }).join("") + (n?.gw ? `<button type="button" class="vm-dot rN" data-vmgw="n${n.gw}" aria-label="GW${n.gw}: to play${n.target ? `, target ${n.target.par}` : ""}"><span class="vm-l" aria-hidden="true">?</span><span class="vm-g">GW${n.gw}</span></button>` : "");
  const rec = V.record || { W: 0, D: 0, L: 0 };
  const nextM = (V.milestones || []).find(m => !m.locked && m.n > run);
  const ms = (V.milestones || []).map(m => {
    const state = m.locked ? "locked" : m.reached ? "got" : m.best ? "best" : "";
    const note = m.locked ? "Counts from next season" : m.reached ? "In this run" : m.best ? "Reached earlier" : m === nextM ? `${m.n - run} win${m.n - run === 1 ? "" : "s"} to go` : `${m.n} wins`;
    return `<li class="vm-ms ${state}"><b>${esc(m.name)}</b><span>${m.n === 38 ? "38–0 season" : `${m.n} in a row`}</span><span class="vm-msn">${note}</span></li>`;
  }).join("");
  const slots = Array.from({ length: 2 }, (_, k) => `<span class="vm-wc${k < held ? " on" : ""}" aria-hidden="true"></span>`).join("");
  return `<div class="panel vm-streak">
      <div class="vm-run"><div><span class="lbl">Winning run</span><b>${head}</b><span class="note">${sub}</span></div>
        <div class="vm-rec" aria-label="Record: won ${rec.W}, drawn ${rec.D}, lost ${rec.L}"><span><b>${rec.W}</b>Won</span><span><b>${rec.D}</b>Drawn</span><span><b>${rec.L}</b>Lost</span></div></div>
      <div class="vm-dots" role="group" aria-label="Results week by week, oldest first">${dots}</div>
      <p class="note vm-key">W win · D draw · L defeat · ? to play · ★ milestone${V.weeks.some(w => w.target?.assumed) ? " · dotted: target assumed (no saved suggestion)" : ""}${V.used ? " · ringed: saved by a wildcard" : ""}</p>
      <div class="vm-cols2">
        <div><h3>Streak Wildcards</h3><div class="vm-wcs" aria-label="Holding ${held} of 2">${slots}<span><b>${held}</b> of 2 held</span></div>
          <p class="note">Earned at each milestone of a run. One saves the run from a defeat; a draw always ends it.${V.used ? ` Used: ${V.used}.` : ""}${V.lost ? ` ${V.lost} missed because you already held 2.` : ""}</p></div>
        <div><h3>Milestones</h3><ul class="vm-mss">${ms}</ul></div>
      </div></div>`;
}

function vVsModel() {
  const V = D.vs_model;
  if (!V || !V.weeks?.length) return stateView({ kind: "empty", title: "You vs the model isn't ready", body: "It needs a finished gameweek with a forecast saved before its deadline. It appears after the next data refresh." });
  const weeks = V.weeks.slice().reverse(), n = V.next;
  const opts = [...(n?.gw ? [[`n${n.gw}`, `GW${n.gw}`]] : []), ...weeks.map(w => [String(w.gw), `GW${w.gw}`])];
  if (!opts.some(([k]) => k === S.vmgw)) S.vmgw = String(weeks[0].gw);
  const w = weeks.find(x => String(x.gw) === S.vmgw);
  return `${vmStreak(V)}<div class="panel vm-intro"><h2>You vs the model</h2>
      <p>Each gameweek your actual points, after hits, against the model's target: its highest projected score for that week from what it suggested before the deadline, rounded. Beat it to win the week.</p>
      <div class="seg vm-gws" role="group" aria-label="Gameweek">${opts.map(([k, l]) => `<button type="button" data-vmgw="${k}" aria-pressed="${k === S.vmgw}">${l}${k[0] === "n" ? " · to play" : ` · ${vmRes[V.weeks.find(x => String(x.gw) === k).res][0]}`}</button>`).join("")}</div>
      ${lineupToggle()}</div>
    ${w ? vmWeek(w) : vmNext(n)}
    ${journalPanel(w ? w.gw : n.gw, !w)}
    ${jSummary()}`;
}
