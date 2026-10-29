// "Make these moves": the plan for one gameweek written out in the order you'd do it on the FPL site.
function movesForGW(g) {
  const sc = scoreMoves(SB.moves), w = sc.weeks.find(x => x.gw === g) || sc.weeks[0];
  return { w, t: w.team, moves: SB.moves.filter(m => m.gw === w.gw) };
}
function formation(xi) { const c = { DEF: 0, MID: 0, FWD: 0 }; xi.forEach(i => { if (c[P[i].pos] != null) c[P[i].pos]++; }); return `${c.DEF}-${c.MID}-${c.FWD}`; }
// order note for a transfer: "tonight" only at FPL's 100% threshold; a fall only matters if it cuts your selling price
function priceNoteFor(prIn, prOut, out) {
  if (prIn >= 100) return "may rise tonight: do this first";
  if (prOut <= -100 && fallCostsYou(out)) return "may fall tonight: sell first";
  if (prIn >= 75) return "rising, not likely tonight";
  if (prOut <= -75 && fallCostsYou(out)) return "falling, not likely tonight";
  return "";
}
function movesSummaryData(g) {
  const { w, t, moves } = movesForGW(g), isNext = w.gw === D.meta.next_gw;
  const pr = id => isNext ? P[id].price_proj?.[0] : null;
  // transfers whose price may move at the next update go first
  const urgent = m => Math.max(pr(m.in) ?? 0, -(pr(m.out) ?? 0));
  const tx = moves.slice().sort((a, b) => urgent(b) - urgent(a)).map(m => ({
    out: m.out, in: m.in, sell: D.squad.some(s => s.id === m.out) && !SB.moves.some(x => x.in === m.out && x.gw < w.gw) ? sellPrice(m.out) : P[m.out].price,
    buy: P[m.in].price, note: priceNoteFor(pr(m.in) ?? 0, pr(m.out) ?? 0, m.out) }));
  const lines = ["GKP", "DEF", "MID", "FWD"].map(pos => [pos, t.xi.filter(i => P[i].pos === pos)]);
  return { gw: w.gw, w, t, tx, lines, isNext };
}
function movesSummaryText(g) {
  const d = movesSummaryData(g), n = i => P[i].name, out = [`FPL LAB plan for GW${d.gw}`];
  out.push(d.tx.length ? `Transfers (${d.tx.length}${d.w.hits ? `, −${4 * d.w.hits} hit` : ", free"}):` : "Transfers: none, roll the free transfer.");
  d.tx.forEach((m, k) => out.push(`${k + 1}. Sell ${n(m.out)} (£${m.sell.toFixed(1)}m) → buy ${n(m.in)} (£${m.buy.toFixed(1)}m)${m.note ? ` [${m.note}]` : ""}`));
  if (d.tx.length) out.push(`Bank after: £${d.w.bank.toFixed(1)}m`);
  out.push(`Starting XI (${formation(d.t.xi)}):`);
  d.lines.forEach(([pos, ids]) => out.push(`  ${pos}: ${ids.map(n).join(", ")}`));
  out.push(`Bench order: ${d.t.bench.map((i, k) => `${k === 0 ? "GK" : k}. ${n(i)}`).join(", ")}`);
  out.push(`Captain: ${n(d.t.cap)} · Vice: ${n(d.t.vice)}`);
  return out.join("\n");
}
function openMovesSummary(g) {
  const d = movesSummaryData(g), n = i => esc(P[i].name);
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <h2>Make these moves · GW${d.gw}</h2>
    <p class="note" style="margin:-8px 0 0">${esc(planName())}. Do them in this order on the FPL site.</p>
    <ol class="howto">
      <li><h3>Transfers ${d.tx.length ? `<span class="muted">${d.tx.length} move${d.tx.length > 1 ? "s" : ""}${d.w.hits ? `, −${4 * d.w.hits} hit` : ", free"}</span>` : ""}</h3>
        ${d.tx.length ? `<div class="moves">${d.tx.map(m => `<div class="move"><span class="out">▼ ${n(m.out)} <span class="muted mono">£${m.sell.toFixed(1)}m</span></span><span class="in">▲ ${n(m.in)} <span class="muted mono">£${m.buy.toFixed(1)}m</span></span>${m.note ? `<span class="pill warn">${m.note}</span>` : ""}</div>`).join("")}</div>
        <p class="note">Bank after: ${money(d.w.bank)}.</p>` : `<p class="muted" style="margin:0">None. Roll the free transfer.</p>`}
        ${d.isNext ? `<a class="btn sm" href="https://fantasy.premierleague.com/transfers" target="_blank" rel="noopener">Open FPL transfers ↗</a>` : ""}</li>
      <li><h3>Pick team <span class="muted">${formation(d.t.xi)}</span></h3>
        <dl class="xi-lines">${d.lines.map(([pos, ids]) => `<dt>${pos}</dt><dd>${ids.map(n).join(", ")}</dd>`).join("")}</dl>
        <p style="margin:6px 0 0"><b>Bench order:</b> ${d.t.bench.map((i, k) => `${k === 0 ? "GK" : k}. ${n(i)}`).join(" · ")}</p></li>
      <li><h3>Captain</h3><p style="margin:0"><b>C</b> ${n(d.t.cap)} · <b>V</b> ${n(d.t.vice)}</p>
        ${d.isNext ? `<a class="btn sm" href="https://fantasy.premierleague.com/my-team" target="_blank" rel="noopener" style="margin-top:8px">Open FPL pick team ↗</a>` : ""}</li>
    </ol>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" id="copyMoves">Copy as text</button><span class="note" id="copyMsg"></span></div>`;
  const dlg = $("#dlg"); dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  $("#copyMoves").onclick = async () => {
    try { await navigator.clipboard.writeText(movesSummaryText(d.gw)); $("#copyMsg").textContent = "Copied."; }
    catch (e) { $("#copyMsg").textContent = "Couldn't copy here. Select the text above instead."; }
  };
}
