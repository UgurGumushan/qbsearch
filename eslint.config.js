import eslint from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";
import globals from "globals";
import tseslint from "typescript-eslint";

const TYPESCRIPT_FILES = [
  "check/**/*.ts",
  "generate/**/*.ts",
  "release/**/*.ts",
  "scripts/**/*.ts",
  "test/**/*.ts",
];

export default tseslint.config(
  {
    ignores: [
      "node_modules/**",
      "external/**",
      "catalog/**",
      "documentation/PLUGINS.md",
      "working/**",
      "dist/**",
      "build/**",
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
