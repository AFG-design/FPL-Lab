// App state, constants and small formatting helpers.
const REPO = "AFG-design/FPL-Lab";
const S = { view: "week", plan: null, fxMode: "att", sort: "xp5", dir: -1, pos: "ALL", team: "ALL", maxp: "", q: "", cmp: [],
  stSort: "xgi90_4", stPos: "ATT", trendTeam: null, pitch: "plan" };
let D, P, T, GWS, PG, MINE, SB;
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const f1 = x => (Math.round((x || 0) * 10) / 10).toFixed(1);
const sgn = x => (x > 0 ? "+" : x < 0 ? "−" : "±") + f1(Math.abs(x));
const money = x => "£" + Number(x).toFixed(1) + "m";
const rankFmt = n => n == null ? "–" : n.toLocaleString("en-GB");
// Club colours: an accent only (thin edges and dots), never a fill. Keyed by team short name.
const CLUB_COL = { ARS: "#db0007", AVL: "#670e36", BOU: "#da291c", BRE: "#e30613", BHA: "#0057b8", CHE: "#034694", COV: "#6cc5ef", CRY: "#1b458f", EVE: "#003399", FUL: "#8c8c8c", HUL: "#f5a12d", IPS: "#3a64a3", LEE: "#ffcd00", LIV: "#c8102e", MCI: "#6cabdd", MUN: "#da291c", NEW: "#8c8c8c", NFO: "#dd0000", SUN: "#eb172b", TOT: "#7a8bb0", WOL: "#fdb913", WHU: "#7a263a", BUR: "#6c1d45" };
const clubCol = p => CLUB_COL[T[p.team]?.short] || "var(--line-strong)";
const store = { get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
const VIEWS = ["week", "afg", "planner", "rivals", "deadlines", "review", "fixtures", "players", "stats", "xptable", "chips", "model", "health"];
{ const v = store.get("fpl.view"); if (VIEWS.includes(v)) S.view = v; }
S.mode = ["balanced", "safe", "chase"].includes(store.get("fpl.mode")) ? store.get("fpl.mode") : "balanced";
S.ptab = ["suggest", "captains", "rules", "drafts"].includes(store.get("fpl.ptab")) ? store.get("fpl.ptab") : "suggest";
// Planner view tabs: your team as it is, one tab per strategy, side by side, and the editor
{ const v = store.get("fpl.pview");   // an older build stored a strategy name here: open Suggested on it
  S.pview = ["mine", "suggest", "compare", "edit"].includes(v) ? v : ["balanced", "safe", "chase"].includes(v) ? "suggest" : "mine";
  S.pstrat = ["balanced", "safe", "chase"].includes(store.get("fpl.pstrat")) ? store.get("fpl.pstrat") : ["balanced", "safe", "chase"].includes(v) ? v : "balanced"; }
S.stab = ["form", "ga", "race", "shots", "sp", "defence", "bonus", "value", "prices", "teams"].includes(store.get("fpl.stab")) ? store.get("fpl.stab") : "form";
S.fxMode = ["fdr", "overall", "att", "def"].includes(store.get("fpl.fxMode")) ? store.get("fpl.fxMode") : "fdr";
S.horizon = [3, 5, 6].includes(store.get("fpl.horizon")) ? store.get("fpl.horizon") : 5;
function setHorizon(h) {
  S.horizon = h; store.set("fpl.horizon", h);
  PG = GWS.slice(0, Math.min(h, GWS.length)); _base = null; _sugg = { key: "", list: [] }; _pairs = { key: "", list: [] };
  if (!PG.includes(SB.gw)) SB.gw = PG[0];
}
if (location.hash && VIEWS.includes(location.hash.slice(1))) S.view = location.hash.slice(1);
