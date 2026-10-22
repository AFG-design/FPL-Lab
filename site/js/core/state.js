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
const store = { get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
const VIEWS = ["week", "planner", "rivals", "review", "fixtures", "players", "stats", "chips", "model"];
{ const v = store.get("fpl.view"); if (VIEWS.includes(v)) S.view = v; }
S.mode = ["balanced", "safe", "chase"].includes(store.get("fpl.mode")) ? store.get("fpl.mode") : "balanced";
S.ptab = ["suggest", "captains", "plans", "rules", "drafts"].includes(store.get("fpl.ptab")) ? store.get("fpl.ptab") : "suggest";
S.stab = ["form", "shots", "sp", "defence", "bonus", "value", "teams"].includes(store.get("fpl.stab")) ? store.get("fpl.stab") : "form";
S.fxMode = ["overall", "att", "def"].includes(store.get("fpl.fxMode")) ? store.get("fpl.fxMode") : "overall";
S.horizon = [3, 5, 6].includes(store.get("fpl.horizon")) ? store.get("fpl.horizon") : 5;
function setHorizon(h) {
  S.horizon = h; store.set("fpl.horizon", h);
  PG = GWS.slice(0, Math.min(h, GWS.length)); _base = null; _sugg = { key: "", list: [] }; _pairs = { key: "", list: [] };
  if (!PG.includes(SB.gw)) SB.gw = PG[0];
}
if (location.hash && VIEWS.includes(location.hash.slice(1))) S.view = location.hash.slice(1);
