// Start-up.
if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
setInterval(() => { const c = $("#cd"); if (c && D) c.textContent = countdown(D.meta.deadline); const d = $("#dlCount"); if (d && D) d.textContent = countdown(D.meta.deadline); const dl = $(".stat.deadline"); if (dl && D) dl.classList.toggle("soon", deadlineSoon(D.meta.deadline)); }, 30000);
load();
