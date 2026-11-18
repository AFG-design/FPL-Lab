// Dark by default, with a light mode. The choice is saved per device.
const THEME = {
  get() { return document.documentElement.dataset.theme === "light" ? "light" : "dark"; },
  set(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("fpl.theme", t); } catch (e) {}
    THEME.paint();
  },
  // the phone's status bar and browser chrome follow the theme: on every paint, so a page that opens in light mode
  // (saved choice) gets the light colour too, not only after a toggle. Colours are the two themes' --bg.
  paint() {
    const light = THEME.get() === "light";
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = light ? "#f3f6f4" : "#0f1a16";
    document.querySelectorAll("[data-theme-toggle]").forEach(b => {
      b.setAttribute("aria-pressed", String(light));
      b.setAttribute("aria-label", "Light mode");
      b.innerHTML = `${icon(light ? "sun" : "moon")}<span>${light ? "Light mode" : "Dark mode"}</span>`;
    });
  },
};
document.querySelectorAll("[data-theme-toggle]").forEach(b => b.addEventListener("click", () => THEME.set(THEME.get() === "light" ? "dark" : "light")));
THEME.paint();
