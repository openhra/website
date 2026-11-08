import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import prettier from "eslint-config-prettier/flat";
import globals from "globals";

export default defineConfig([
  globalIgnores([
    "**/node_modules/**",
    "**/dist/**",
    "**/coverage/**",
    "**/.git/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "**/.vercel/**",
    "**/.lanes/**",
    "docs/**",
    "**/work-notes/**",
    "plans/data/coverage/**",
    "tests/reference/**",
    "**/fixtures/**/*",
    "!**/fixtures/**/",
    "!**/fixtures/**/*.{js,mjs,cjs}",
  ]),
  {
    files: ["**/*.{js,mjs,cjs}"],
    extends: [js.configs.recommended],
    languageOptions: { ecmaVersion: "latest" },
    linterOptions: { reportUnusedDisableDirectives: "error" },
    rules: { "no-nested-ternary": "error" },
  },
  {
    files: ["openhra/*.js", "plans/*.js", "plans/brand/**/*.js"],
    languageOptions: { sourceType: "script", globals: globals.browser },
  },
  {
    files: ["**/api/*.js", "**/*.mjs"],
    languageOptions: { sourceType: "module", globals: globals.nodeBuiltin },
  },
  {
    files: ["**/*.cjs"],
    languageOptions: { sourceType: "commonjs", globals: globals.node },
  },
  prettier,
]);
