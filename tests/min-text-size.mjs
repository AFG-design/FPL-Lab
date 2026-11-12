// FL-123: no text under 11px. Every font-size set in the stylesheets (px values and the size tokens) must be at least
// 11px. This is the cheap static half; scripts/contrast_check.py measures what is rendered (em sizes, the browser's
// "smaller" defaults) and contrast, in a browser, on the Check site workflow.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";

const dir = new URL("../site/styles/", import.meta.url);
const MIN = 11;

test(`every font-size in site/styles is ${MIN}px or more`, () => {
  const small = [];
  for (const f of readdirSync(dir).filter(n => n.endsWith(".css"))) {
    readFileSync(new URL(f, dir), "utf8").split("\n").forEach((line, i) => {
      for (const m of line.matchAll(/(?:font-size|--fs-[\w-]+)\s*:\s*([\d.]+)px/g))
        if (parseFloat(m[1]) < MIN) small.push(`${f}:${i + 1} ${m[0]}`);
    });
  }
  assert.deepEqual(small, []);
});
