// Start-up.
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
setInterval(() => { const c = $("#cd"); if (c && D) c.textContent = countdown(D.meta.deadline); }, 30000);
load();
