import eslint from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";
import globals from "globals";
import tseslint from "typescript-eslint";

// Source of truth for TS roots: tool/core/repo.ts TYPESCRIPT_DIRS (+ packages/website).
const TYPESCRIPT_FILES = ["test/**/*.ts", "tool/**/*.ts", "packages/website/**/*.{ts,tsx}"];

export default tseslint.config(
  {
    ignores: [
      "node_modules/**",
      "catalog/**",
      "documentation/PLUGINS.md",
      "working/**",
      "dist/**",
      "build/**",
      "**/.next/**",
      ".opencode/**",
      ".venv/**",
      ".ruff_cache/**",
      "**/__pycache__/**",
    ],
  },
  eslint.configs.recommended,
  {
    files: TYPESCRIPT_FILES,
    extends: [tseslint.configs.strictTypeChecked, tseslint.configs.stylisticTypeChecked],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
      globals: {
        ...globals.bun,
        ...globals.node,
        ...globals.browser,
      },
    },
    rules: {
      "@typescript-eslint/restrict-template-expressions": [
        "error",
        {
          allowNumber: true,
        },
      ],
    },
  },
  eslintConfigPrettier,
);
