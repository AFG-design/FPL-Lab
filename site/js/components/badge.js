// Club badges: the official crests, saved into the site by the build (badges/{code}.png).
// If one is missing, a monogram in the club's colour takes its place.
const CLUB_COLOUR = { ARS: "#EF0107", AVL: "#670E36", BHA: "#0057B8", BOU: "#DA291C", BRE: "#E30613", BUR: "#6C1D45", CHE: "#034694",
  COV: "#59CBE8", CRY: "#1B458F", EVE: "#003399", FUL: "#222222", HUL: "#F5A12D", IPS: "#3A64A3", LEE: "#FFCD00", LEI: "#003090",
  LIV: "#C8102E", MCI: "#6CABDD", MUN: "#DA291C", NEW: "#241F20", NFO: "#DD0000", SHU: "#EE2737", SOU: "#D71920", SUN: "#EB172B",
  TOT: "#132257", WHU: "#7A263A", WOL: "#FDB913", MID: "#E21B23", NOR: "#00A650", WAT: "#FBEE23", WBA: "#122F67", LUT: "#F78F1E" };
function badge(tid, size = 28) {
  const t = T[tid]; if (!t) return "";
  const has = (D.meta.badges || []).includes(t.code);
  const mono = `<i aria-hidden="true">${esc(t.short)}</i>`;
  return `<span class="crest ${has ? "" : "nob"}" style="--club:${CLUB_COLOUR[t.short] || "#556"};--sz:${size}px" title="${esc(t.name)}">${has ? `<img src="badges/${t.code}.png" alt="" width="${size}" height="${size}" loading="lazy" decoding="async" onerror="this.parentNode.classList.add('nob');this.remove()">` : ""}${mono}</span>`;
}
