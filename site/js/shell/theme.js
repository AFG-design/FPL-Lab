// Dark by default, with a light mode. The choice is saved per device.
const THEME = {
  get() { return document.documentElement.dataset.theme === "light" ? "light" : "dark"; },
  set(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("fpl.theme", t); } catch (e) {}
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = t === "light" ? "#f3f6f4" : "#0f1a16";
    THEME.paint();
  },
  paint() {
    const light = THEME.get() === "light";
    document.querySelectorAll("[data-theme-toggle]").forEach(b => {
      b.setAttribute("aria-pressed", String(light));
      b.setAttribute("aria-label", "Light mode");
      b.innerHTML = `${icon(light ? "sun" : "moon")}<span>${light ? "Light mode" : "Dark mode"}</span>`;
    });
  },
};
document.querySelectorAll("[data-theme-toggle]").forEach(b => b.addEventListener("click", () => THEME.set(THEME.get() === "light" ? "dark" : "light")));
THEME.paint();
