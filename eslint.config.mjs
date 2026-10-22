// The site's scripts are classic <script defer> files that share one global scope,
// so cross-file names are checked by scripts/check.mjs (which sees them all together).
import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["site/vendor/**", "node_modules/**"] },
  js.configs.recommended,
  {
    files: ["site/**/*.js"],
    languageOptions: { ecmaVersion: 2023, sourceType: "script", globals: { ...globals.browser } },
    rules: {
      "no-undef": "off",
      "no-unused-vars": "off",
      "no-redeclare": "off",
      "no-empty": ["error", { allowEmptyCatch: true }],
      "eqeqeq": ["error", "smart"],
      "no-var": "error",
      "prefer-const": ["warn", { destructuring: "all" }],
    },
  },
  {
    files: ["site/sw.js"],
    languageOptions: { globals: { ...globals.serviceworker } },
  },
  {
    files: ["scripts/**/*.mjs", "eslint.config.mjs"],
    languageOptions: { sourceType: "module", globals: { ...globals.node } },
  },
];
