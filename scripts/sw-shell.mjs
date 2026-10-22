// Rewrites the offline file list in site/sw.js from index.html and bumps the cache version.
// Run after adding or removing a script or stylesheet: npm run sw
import { readFileSync, writeFileSync } from "node:fs";
const html = readFileSync("site/index.html", "utf8");
const files = [
  "./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png",
  ...[...html.matchAll(/<link rel="(?:stylesheet|preload)" href="([^":]+)"/g)].map(m => m[1]),
  ...[...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]),
];
let sw = readFileSync("site/sw.js", "utf8");
sw = sw.replace(/const SHELL = \[[\s\S]*?\];/, `const SHELL = [\n${files.map(f => `  "${f}"`).join(",\n")}\n];`);
sw = sw.replace(/"fpl-lab-v(\d+)"/, (_, n) => `"fpl-lab-v${+n + 1}"`);
writeFileSync("site/sw.js", sw);
console.log(`sw.js: ${files.length} files, ${sw.match(/"fpl-lab-v\d+"/)[0]}`);
