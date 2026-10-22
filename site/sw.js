// FPL Lab offline cache: the page and your last data stay available without signal.
const CACHE = "fpl-lab-v8";
const SHELL = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "icon-192.png",
  "icon-512.png",
  "vendor/fonts/inter-var-latin.woff2",
  "styles/tokens.css",
  "styles/base.css",
  "styles/layout.css",
  "styles/components.css",
  "styles/views.css",
  "js/core/state.js",
  "js/core/model.js",
  "js/components/ui.js",
  "js/data/load.js",
  "js/shell/theme.js",
  "js/shell/nav.js",
  "js/components/pitch.js",
  "js/core/plan.js",
  "js/views/week.js",
  "js/views/planner.js",
  "js/views/rivals.js",
  "js/views/fixtures.js",
  "js/views/players.js",
  "js/views/stats.js",
  "js/views/chips.js",
  "js/views/review.js",
  "js/views/model.js",
  "js/components/player-sheet.js",
  "js/shell/events.js",
  "js/components/explain.js",
  "js/data/github.js",
  "js/components/search.js",
  "js/main.js"
];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.origin === location.origin) {
    // network first, so fresh data and new versions always win; cache as a fallback
    e.respondWith(fetch(e.request).then(r => {
      const copy = r.clone();
      const key = url.pathname.endsWith("data.json") ? new Request("data.json") : e.request;
      caches.open(CACHE).then(c => c.put(key, copy));
      return r;
    }).catch(() => caches.match(url.pathname.endsWith("data.json") ? new Request("data.json") : e.request).then(r => r || caches.match("index.html"))));
  } else if (url.hostname === "fantasy.premierleague.com" && url.pathname.includes("/shirts/")) {
    // show the cached kit instantly but always re-check, so kit updates come through
    e.respondWith(caches.open(CACHE).then(c => c.match(e.request).then(hit => {
      const net = fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    })));
  }
});
