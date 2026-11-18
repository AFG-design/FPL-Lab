// Shared, read-only helpers for the three UI redesign prototypes. Prototype only: nothing in site/ loads this.
// Reads window.SAMPLE (sample-data.js). "Now" is frozen at the snapshot's build time so countdowns and
// screenshots are stable; every prototype labels its data as a sample.
(function () {
  const S = window.SAMPLE;
  if (!S) throw new Error("sample-data.js missing: run shared/extract.py first");
  const P = Object.fromEntries(S.players.map(p => [p.id, p]));
  const T = S.teams;
  const G = S.gws[0];                       // next gameweek (the one the decisions are for)
  const NOW = new Date(S.meta.built);

  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const money = m => `£${Number(m).toFixed(1)}m`;
  const num = (v, d = 1) => v == null ? "–" : Number(v).toFixed(d);
  const rank = r => r == null ? "–" : Number(r).toLocaleString("en-GB");
  const short = r => r >= 1e6 ? (r / 1e6).toFixed(1) + "m" : r >= 1e3 ? Math.round(r / 1e3) + "k" : String(r);
  const pct = v => v == null ? "–" : Math.round(v * 100) + "%";

  function countdown() {
    const ms = new Date(S.meta.deadline) - NOW;
    const d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4);
    return { d, h, m, text: d ? `${d}d ${h}h` : `${h}h ${m}m` };
  }
  const deadlineText = () => new Date(S.meta.deadline).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });

  // fixtures for a team in a gameweek: [{opp:"FUL", home:true, fdr:2}] (empty list = blank gameweek)
  const fx = (team, gw) => (T[team]?.fx?.[gw] || []).map(([o, h, f]) => ({ opp: T[o].short, home: h, fdr: f }));
  const fxLabel = (team, gw) => { const f = fx(team, gw); return f.length ? f.map(x => `${x.opp} (${x.home ? "H" : "A"})`).join(", ") : "Blank"; };
  const badge = team => `../../../site/badges/${T[team].code}.png`;
  const teamShort = team => T[team].short;

  const xp = (id, gw = G) => P[id]?.xp?.[gw] ?? 0;
  const POS_ORDER = { GKP: 0, DEF: 1, MID: 2, FWD: 3 };
  const squad = () => {
    const L = S.lineup;
    const row = id => ({ ...P[id], cap: id === L.captain, vice: id === L.vice });
    const xi = L.xi.map(row).sort((a, b) => POS_ORDER[a.pos] - POS_ORDER[b.pos]);
    return { xi, bench: L.bench.map(row), lines: ["GKP", "DEF", "MID", "FWD"].map(pos => xi.filter(p => p.pos === pos)), xp: L.xp_best, captain: P[L.captain], vice: P[L.vice] };
  };
  const captains = () => S.lineup.captain_options.slice(0, 4).map(c => ({ ...P[c.id], cxp: c.xp * 2 }));

  // the strategies, labelled the way the live site labels them
  const STRATS = [["balanced", "Balanced", "Best projected points, never takes a hit"], ["safe", "Play safe", "Backs proven, owned players, never takes a hit"], ["chase", "Chase rank", "May back differentials; can take a −4"]];
  const strategies = () => STRATS.map(([k, name, blurb]) => {
    const pl = S.plans[k];
    // pair each sale with a purchase in the same position (the plan stores ins and outs as two id lists)
    const pairUp = w => { const ins = w.in.map(i => P[i]); return w.out.map(o => { const out = P[o]; const j = ins.findIndex(p => p && p.pos === out.pos); return [out, j >= 0 ? ins.splice(j, 1)[0] : ins.shift()]; }); };
    const moves = pl.weeks.filter(w => w.in.length).map(w => ({ gw: w.gw, hits: w.hits, pairs: pairUp(w) }));
    const first = pl.weeks[0];
    return { key: k, name, blurb, gain: pl.vs_none, total: pl.xp_total, weeks: pl.weeks, moves, nowAction: first.in.length ? `${first.in.length} transfer${first.in.length > 1 ? "s" : ""}` : "Roll the free transfer" };
  });

  const players = ({ pos = "ALL", sort = "xp5", limit = 40 } = {}) =>
    S.players.filter(p => pos === "ALL" || p.pos === pos).sort((a, b) => (b[sort] ?? 0) - (a[sort] ?? 0)).slice(0, limit);
  const inSquad = id => S.squad.some(s => s.id === id);

  // team fixture run over the plan window, easiest first (average FDR)
  const fixtureGrid = () => Object.entries(T).map(([id, t]) => {
    const cells = S.gws.map(g => ({ gw: g, list: fx(id, g) }));
    const all = cells.flatMap(c => c.list.map(f => f.fdr));
    return { id: +id, short: t.short, name: t.name, code: t.code, cells, avg: all.reduce((a, b) => a + b, 0) / (all.length || 1) };
  }).sort((a, b) => a.avg - b.avg);

  const statusText = p => p.status === "a" ? null : p.news || (p.chance != null ? `${p.chance}% chance of playing` : "Flagged");

  const ICON = {
    home: '<path d="M4 11l8-7 8 7v9h-5v-6H9v6H4z"/>', planner: '<path d="M4 5h16v14H4zM4 10h16M10 10v9"/>', players: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    fixtures: '<path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4"/>', rivals: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM12 13v4M8 21h8M5 5H3v2a3 3 0 0 0 3 3M19 5h2v2a3 3 0 0 1-3 3"/>',
    more: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5"/>', moon: '<path d="M20 14A8 8 0 1 1 10 4a6 6 0 0 0 10 10z"/>', arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    chips: '<path d="M12 3l2.6 5.6 6 .6-4.5 4 1.3 6L12 16l-5.4 3.2 1.3-6-4.5-4 6-.6z"/>', model: '<path d="M4 19l5-6 4 3 7-9"/>', close: '<path d="M6 6l12 12M18 6L6 18"/>',
    up: '<path d="M6 15l6-6 6 6"/>', swap: '<path d="M7 7h12l-3-3M17 17H5l3 3"/>', filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  };
  const icon = (k, cls = "ic") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[k] || ""}</svg>`;

  window.PROTO = { icon, S, P, T, G, NOW, esc, money, num, rank, short, pct, countdown, deadlineText, fx, fxLabel, badge, teamShort, xp, squad, captains, strategies, players, inSquad, fixtureGrid, statusText,
    route() { const [v, arg] = (location.hash.slice(1) || "home").split("/"); return { view: v, arg }; },
    theme() { const t = new URLSearchParams(location.search).get("theme"); if (t) document.documentElement.dataset.theme = t; },
  };
})();
