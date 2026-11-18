// Shared, read-only helpers for the round-2 UI redesign prototypes. Prototype only: nothing in site/ loads this.
// Reads window.SAMPLE (sample-data.js). "Now" is frozen at the snapshot's build time so countdowns and screenshots are
// stable; every prototype labels its data as a sample. No network: fonts and club badges are read from site/ by
// relative path, and shirts (FPL's CDN) are deliberately not used.
(function () {
  const S = window.SAMPLE;
  if (!S) throw new Error("sample-data.js missing: run shared/extract.py first");
  const P = Object.fromEntries(S.players.map(p => [p.id, p]));
  const T = S.teams;
  const G = S.gws[0];
  const NOW = new Date(S.meta.built);

  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const money = m => `£${Number(m).toFixed(1)}m`;
  const num = (v, d = 1) => v == null ? "–" : Number(v).toFixed(d);
  const rank = r => r == null ? "–" : Number(r).toLocaleString("en-GB");
  const short = r => r >= 1e6 ? (r / 1e6).toFixed(1) + "m" : r >= 1e3 ? Math.round(r / 1e3) + "k" : String(r);
  const pct = v => v == null ? "–" : Math.round(v * 100) + "%";
  const sgn = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d);

  const until = iso => { const ms = new Date(iso) - NOW; const d = Math.floor(ms / 864e5), h = Math.floor(ms % 864e5 / 36e5), m = Math.floor(ms % 36e5 / 6e4); return { d, h, m, text: d ? `${d}d ${h}h` : `${h}h ${m}m` }; };
  const countdown = () => until(S.meta.deadline);
  const when = (iso, o = { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) => new Date(iso).toLocaleString("en-GB", { ...o, timeZone: "Europe/London" });
  const deadlineText = () => when(S.meta.deadline);
  const ago = iso => { if (!iso) return "never"; const m = Math.round((NOW - new Date(iso)) / 6e4); return m < 60 ? `${m} min ago` : m < 2880 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} days ago`; };

  // fixtures for a team in a gameweek: [{opp:"FUL", home:true, fdr:2}] (empty list = blank gameweek)
  const fx = (team, gw) => (T[team]?.fx?.[gw] || []).map(([o, h, f]) => ({ opp: T[o].short, home: h, fdr: f }));
  const fxLabel = (team, gw) => { const f = fx(team, gw); return f.length ? f.map(x => `${x.opp} (${x.home ? "H" : "A"})`).join(", ") : "Blank"; };
  const fxShort = (team, gw) => { const f = fx(team, gw); return f.length ? f.map(x => x.home ? x.opp : x.opp.toLowerCase()).join(" + ") : "—"; };
  const badge = team => `../../../site/badges/${T[team].code}.png`;
  const teamShort = team => T[team].short;

  const xp = (id, gw = G) => P[id]?.xp?.[gw] ?? 0;
  const POS_ORDER = { GKP: 0, DEF: 1, MID: 2, FWD: 3 };
  const POS_NAME = { GKP: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" };
  const squad = () => {
    const L = S.lineup;
    const row = id => ({ ...P[id], cap: id === L.captain, vice: id === L.vice });
    const xi = L.xi.map(row).sort((a, b) => POS_ORDER[a.pos] - POS_ORDER[b.pos]);
    return { xi, bench: L.bench.map(row), lines: ["GKP", "DEF", "MID", "FWD"].map(pos => xi.filter(p => p.pos === pos)), xp: L.xp_best, captain: P[L.captain], vice: P[L.vice] };
  };
  // the squad as a given strategy plans it for a given gameweek (xi/bench/captain stored per week in the plan)
  const planSquad = (strat, gw) => {
    const w = S.plans[strat].weeks.find(x => x.gw === gw);
    const row = id => ({ ...P[id], cap: id === w.captain, vice: id === w.vice, isNew: false });
    const xi = w.xi.map(row).sort((a, b) => POS_ORDER[a.pos] - POS_ORDER[b.pos]);
    return { week: w, xi, bench: w.bench.map(row), lines: ["GKP", "DEF", "MID", "FWD"].map(pos => xi.filter(p => p.pos === pos)) };
  };
  const captains = () => S.lineup.captain_options.slice(0, 5).map(c => ({ ...P[c.id], cxp: c.xp * 2 }));

  const STRATS = [["balanced", "Balanced", "Goes for the most projected points. Never takes a hit."],
    ["safe", "Play safe", "Sticks close to what managers near your rank own. Never takes a hit."],
    ["chase", "Chase rank", "Gives up at most 2 projected points to back differentials. May take a −4."]];
  const strategies = () => STRATS.map(([k, name, blurb]) => {
    const pl = S.plans[k];
    const pairUp = w => { const ins = w.in.map(i => P[i]); return w.out.map(o => { const out = P[o]; const j = ins.findIndex(p => p && p.pos === out.pos); return [out, j >= 0 ? ins.splice(j, 1)[0] : ins.shift()]; }); };
    const moves = pl.weeks.filter(w => w.in.length).map(w => ({ gw: w.gw, hits: w.hits, pairs: pairUp(w) }));
    const first = pl.weeks[0];
    return { key: k, name, blurb, gain: pl.vs_none, total: pl.xp_total, weeks: pl.weeks, moves, ftLeft: pl.ft_left,
      nowAction: first.in.length ? `${first.in.length} transfer${first.in.length > 1 ? "s" : ""}` : "Roll the free transfer" };
  });

  const players = ({ pos = "ALL", sort = "xp5", limit = 40 } = {}) =>
    S.players.filter(p => pos === "ALL" || p.pos === pos).sort((a, b) => (b[sort] ?? 0) - (a[sort] ?? 0)).slice(0, limit);
  const inSquad = id => S.squad.some(s => s.id === id);

  const fixtureGrid = () => Object.entries(T).map(([id, t]) => {
    const cells = S.gws.map(g => ({ gw: g, list: fx(id, g) }));
    const all = cells.flatMap(c => c.list.map(f => f.fdr));
    return { id: +id, short: t.short, name: t.name, code: t.code, cells, avg: all.reduce((a, b) => a + b, 0) / (all.length || 1), owned: S.squad.some(s => P[s.id]?.team === +id) };
  }).sort((a, b) => a.avg - b.avg);

  // status text tests the same fields the live site uses (status, news, chance); null = available with no flag
  const statusText = p => p.status === "a" ? null : p.news || (p.chance != null ? `${p.chance}% chance of playing` : "Flagged, no chance given (assumed doubtful)");

  // the "Why x xP" parts, in the live sheet's own labels. null = no breakdown in the snapshot (shown as such, not as zero)
  const PART_LABEL = { mins: "Appearance", goals: "Goals", assists: "Assists", cs: "Clean sheet", gc: "Conceded", saves: "Saves", dc: "Def. contrib.", bonus: "Bonus", cards: "Cards", appear_adj: "Appearance adj." };
  const breakdown = p => p.detail ? Object.entries(p.detail.xp).filter(([, v]) => Math.abs(v) >= 0.005).map(([k, v]) => ({ key: k, label: PART_LABEL[k] || k, v })) : null;
  // outcomes for the next GW: dist = [P(10+), P(6+), P(2 or fewer), likely low, likely high] (8 in 10 inside low–high)
  const outcomes = p => p.dist ? { p10: p.dist[0], p6: p.dist[1], p2: p.dist[2], lo: p.dist[3], hi: p.dist[4] } : null;

  // data-source keys as people say them (an unknown key is shown as it is, not hidden)
  const SRC = { fpl: "FPL API", understat: "Understat", odds: "Match odds", player_odds: "Player odds", fixture_odds: "Fixture odds", crowd: "Managers sample", prices: "Price changes", news: "News", status: "Status log", template: "Template", deadline: "Deadline", awards: "Awards" };
  const srcName = k => SRC[k] || k;
  const PHONE = () => matchMedia("(max-width: 899px)").matches;
  // a right-edge fade on any sideways-scrolling box, only while it actually overflows (audit #12, #17)
  const fadeScrollers = sel => document.querySelectorAll(sel).forEach(el => { const f = () => el.classList.toggle("fade-r", el.scrollWidth > el.clientWidth + 2 && el.scrollLeft + el.clientWidth < el.scrollWidth - 2); f(); el.onscroll = f; });
  const ICON = {
    home: '<path d="M4 11l8-7 8 7v9h-5v-6H9v6H4z"/>', planner: '<path d="M4 5h16v14H4zM4 10h16M10 10v9"/>', players: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    fixtures: '<path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4"/>', rivals: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM12 13v4M8 21h8M5 5H3v2a3 3 0 0 0 3 3M19 5h2v2a3 3 0 0 1-3 3"/>',
    more: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5"/>', moon: '<path d="M20 14A8 8 0 1 1 10 4a6 6 0 0 0 10 10z"/>', arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    chips: '<path d="M12 3l2.6 5.6 6 .6-4.5 4 1.3 6L12 16l-5.4 3.2 1.3-6-4.5-4 6-.6z"/>', model: '<path d="M4 19l5-6 4 3 7-9"/>', close: '<path d="M6 6l12 12M18 6L6 18"/>',
    up: '<path d="M6 15l6-6 6 6"/>', down: '<path d="M6 9l6 6 6-6"/>', swap: '<path d="M7 7h12l-3-3M17 17H5l3 3"/>', filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
    clock: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>', review: '<path d="M4 19h16M6 16l4-5 3 3 5-7"/>', health: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
    star: '<path d="M12 4l2.4 5 5.6.6-4.2 3.8 1.2 5.6-5-2.9-5 2.9 1.2-5.6L4 9.6 9.6 9z"/>', back: '<path d="M15 6l-6 6 6 6"/>', check: '<path d="M5 12l5 5 9-10"/>', bolt: '<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>',
    school: '<path d="M3 9l9-5 9 5-9 5zM7 11v5c3 2 7 2 10 0v-5"/>', bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5V16h8v-2.5A6 6 0 0 0 12 3z"/>', vs: '<path d="M4 5h6v14H4zM14 5h6v14h-6z"/>',
  };
  const icon = (k, cls = "ic") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[k] || ""}</svg>`;

  // the live site's sections, in its order (tabs stay where they are; CLAUDE.md "Tabs and planner")
  const NAV = [
    ["Matchday", [["home", "This week", "home"], ["planner", "Planner", "planner"], ["rivals", "Rivals", "rivals"], ["deadlines", "Deadlines", "clock"]]],
    ["AFG", [["afg", "AFG suggestion", "bulb"]]],
    ["Analysis", [["players", "Players", "players"], ["fixtures", "Fixtures", "fixtures"], ["school", "FPL School", "school"]]],
    ["Season", [["chips", "Chips", "star"], ["review", "Review", "review"], ["vsmodel", "You vs the model", "vs"], ["model", "Model", "model"]]],
  ];
  const BUILT = ["home", "planner", "players", "fixtures", "rivals", "model"];

  const sampleNote = () => `Sample data: FPL LAB snapshot, ${when(S.meta.built, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}. Not live; mini-league managers anonymised.`;

  window.PROTO = { icon, S, P, T, G, NOW, esc, money, num, rank, short, pct, sgn, until, countdown, when, deadlineText, ago, fx, fxLabel, fxShort, badge, teamShort, xp,
    POS_NAME, squad, planSquad, captains, strategies, players, inSquad, fixtureGrid, statusText, breakdown, outcomes, srcName, PHONE, fadeScrollers, NAV, BUILT, sampleNote,
    route() { const [v, arg] = (location.hash.slice(1) || "home").split("/"); return { view: v, arg }; },
    theme() { const t = new URLSearchParams(location.search).get("theme"); if (t) document.documentElement.dataset.theme = t; },
  };
})();
