// Whole-app checks that per-file linting can't do, because the site's scripts share one global scope:
//  1. every script in index.html parses;
//  2. read together in page order, no name is used without being defined, and none is declared twice;
//  3. every local file referenced by index.html, the manifest and the service worker exists.
// Run: npm run check
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { Linter } from "eslint";
import globals from "globals";

const SITE = "site";
const html = readFileSync(join(SITE, "index.html"), "utf8");
const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
let failed = 0;
const fail = msg => { failed++; console.error("✗ " + msg); };

// 1 + 2: lint the scripts as one program, then map messages back to their files
const files = scripts.map(path => ({ path, text: readFileSync(join(SITE, path), "utf8") }));
let offset = 0;
const spans = files.map(f => { const lines = f.text.split("\n").length; const s = { path: f.path, from: offset + 1, to: offset + lines }; offset += lines; return s; });
const where = line => { const s = spans.find(x => line >= x.from && line <= x.to); return s ? `${s.path}:${line - s.from + 1}` : `line ${line}`; };
const linter = new Linter();
const messages = linter.verify(files.map(f => f.text).join("\n"), {
  languageOptions: { ecmaVersion: 2023, sourceType: "script", globals: { ...globals.browser } },
  rules: { "no-undef": "error", "no-redeclare": "error", "no-dupe-keys": "error", "no-unreachable": "error" },
});
for (const m of messages) fail(`${where(m.line)}  ${m.message}`);

// 3: local references
const refs = new Set(scripts);
for (const m of html.matchAll(/(?:href|src)="([^"#:]+)"/g)) refs.add(m[1]);
const manifest = JSON.parse(readFileSync(join(SITE, "manifest.webmanifest"), "utf8"));
manifest.icons.forEach(i => refs.add(i.src));
const sw = readFileSync(join(SITE, "sw.js"), "utf8");
const shell = JSON.parse(sw.match(/const SHELL = (\[[\s\S]*?\]);/)[1]);
shell.filter(p => p !== "./").forEach(p => refs.add(p));
for (const r of refs) if (!existsSync(join(SITE, r.split("?")[0]))) fail(`missing file: site/${r}`);
for (const s of scripts.concat(["styles/"])) if (!shell.some(p => p === s || (s.endsWith("/") && p.startsWith(s)))) fail(`not cached offline by sw.js: ${s}`);

if (failed) { console.error(`\n${failed} problem(s)`); process.exit(1); }
console.log(`✓ ${scripts.length} scripts checked together, ${refs.size} local files present, all cached offline`);
