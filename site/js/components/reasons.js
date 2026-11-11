// Reasons for the decision journal (D5b): a "Why?" on moves you make and a "Why not?" on the model's suggestions you
// skip, as one or more of six tags plus an optional short note.
// Where: Home's Transfers card (your planned moves for next GW), the model's suggestion for the week to come on the
// You vs the model tab, and every row of the decision journal (after the deadline too, marked "added after").
// Stored in this browser (localStorage "fpl.reasons") and, when sync is on, in the sync file with the plan and the
// watchlist. Merged item by item, newest edit wins, so tagging on two devices never loses either. Clearing a reason keeps
// an empty item with its time, so the clear also wins over an older copy on another device.
// Missing / ambiguous: storage unavailable -> kept for this page visit only, and the dialog says so; sync off -> this
// device only, and the dialog says so; a reason for a move that isn't in the final journal (the suggestion changed
// before the deadline) is kept and not shown against a different move. Notes are plain text, always escaped.
const REASON_TAGS = [["minutes", "Minutes risk"], ["prefer", "Prefer another player"], ["price", "Price"],
  ["gut", "Gut feel"], ["news", "Team news"], ["fixtures", "Fixtures"]];
const REASON_WORD = Object.fromEntries(REASON_TAGS);
const REASONS = (() => {
  const s = store.get("fpl.reasons");
  return s && s.items && typeof s.items === "object" ? s : { items: {}, updated: 0 };
})();
const reasonKey = (gw, out, inn) => `${gw}:${out}-${inn}`;
const reasonOf = (gw, out, inn) => { const r = REASONS.items[reasonKey(gw, out, inn)]; return r && (r.tags?.length || r.note) ? r : null; };
const REASON_STORE_OK = (() => { try { localStorage.setItem("fpl.t", "1"); localStorage.removeItem("fpl.t"); return true; } catch (e) { return false; } })();

// a deadline still to come: only next GW's, before its deadline
const beforeDeadline = gw => gw === D.meta.next_gw && D.meta.deadline && Date.now() < Date.parse(D.meta.deadline);

function setReason(gw, out, inn, kind, tags, note) {
  const k = reasonKey(gw, out, inn);
  REASONS.items[k] = { gw, out, in: inn, kind, tags: tags.filter(t => REASON_WORD[t]), note: String(note || "").slice(0, 200),
    t: Date.now(), late: !beforeDeadline(gw) };
  REASONS.updated = Date.now(); store.set("fpl.reasons", REASONS);
  if (typeof syncPush === "function") syncPush();
}
// sync: item by item, newest wins. Returns true when anything here changed.
function mergeReasons(remote) {
  if (!remote || !remote.items) return false;
  let changed = false;
  Object.entries(remote.items).forEach(([k, r]) => {
    if (r && (r.t || 0) > (REASONS.items[k]?.t || 0)) { REASONS.items[k] = r; changed = true; }
  });
  if (changed) { REASONS.updated = Math.max(REASONS.updated, remote.updated || 0); store.set("fpl.reasons", REASONS); }
  return changed;
}

// the button: shows the saved tags (and note) once there are any
function reasonBtn(gw, out, inn, kind) {
  const r = reasonOf(gw, out, inn), ask = kind === "whynot" ? "Why not?" : "Why?";
  const said = r ? `${r.tags.map(t => REASON_WORD[t]).join(", ")}${r.note ? `${r.tags.length ? ": " : ""}“${esc(r.note)}”` : ""}` : "";
  return `<button type="button" class="rs-btn${r ? " set" : ""}" data-reason="${gw}:${out}:${inn}:${kind}" aria-label="${ask} ${esc(P[out]?.name || "")} out, ${esc(P[inn]?.name || "")} in${r ? `. Saved: ${said.replace(/<[^>]+>/g, "")}` : ""}">${r ? `<span class="rs-k">${kind === "whynot" ? "Skipped:" : "Why:"}</span> ${said}${r.late ? ' <span class="muted">(added after the deadline)</span>' : ""}` : `+ ${ask}`}</button>`;
}

function openReason(gw, out, inn, kind) {
  const r = REASONS.items[reasonKey(gw, out, inn)] || { tags: [], note: "" };
  const sel = new Set(r.tags || []);
  const ask = kind === "whynot" ? "Why not make this move?" : "Why this move?";
  const where = !REASON_STORE_OK ? "This browser can't save, so the reason is kept until you close the page."
    : typeof syncReady === "function" && syncReady() ? "Saved on this device and synced with your plan."
    : "Saved on this device only. Turn on Sync plan to keep it on your other devices too.";
  $("#dlgBody").innerHTML = `<button class="x" aria-label="Close" id="dlgX">×</button>
    <h2>${ask}</h2>
    <p class="rs-move"><span class="out">▼ ${esc(P[out]?.name || "?")}</span> <span class="in">▲ ${esc(P[inn]?.name || "?")}</span> <span class="muted">GW${gw}</span></p>
    <div class="rs-tags" role="group" aria-label="Reasons">${REASON_TAGS.map(([k, l]) => `<button type="button" class="chipbtn" data-rtag="${k}" aria-pressed="${sel.has(k)}">${l}</button>`).join("")}</div>
    <label class="rs-note">Note (optional)<textarea id="rsNote" maxlength="200" rows="2" placeholder="e.g. press conference sounded like rotation">${esc(r.note || "")}</textarea></label>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" id="rsSave">Save</button>${reasonOf(gw, out, inn) ? '<button class="btn" id="rsClear">Clear</button>' : ""}</div>
    <p class="note">${where}${beforeDeadline(gw) ? "" : " This deadline has passed, so it's marked as added after the deadline."}</p>`;
  const dlg = $("#dlg"); if (!dlg.open) dlg.showModal();
  $("#dlgX").onclick = () => dlg.close();
  document.querySelectorAll("#dlgBody [data-rtag]").forEach(b => b.onclick = () => {
    const k = b.dataset.rtag; if (sel.has(k)) sel.delete(k); else sel.add(k); b.setAttribute("aria-pressed", sel.has(k));
  });
  $("#rsSave").onclick = () => { setReason(gw, out, inn, kind, [...sel], $("#rsNote").value.trim()); dlg.close(); render(); };
  const cl = $("#rsClear"); if (cl) cl.onclick = () => { setReason(gw, out, inn, kind, [], ""); dlg.close(); render(); };
}
