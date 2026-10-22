// FPL Lab offline cache: the page and your last data stay available without signal.
const CACHE = "fpl-lab-v3";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png"];
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
    e.respondWith(caches.open(CACHE).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { c.put(e.request, r.clone()); return r; }))));
  }
});
