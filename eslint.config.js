import eslint from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";
import jsdoc from "eslint-plugin-jsdoc";
import globals from "globals";
import tseslint from "typescript-eslint";

// Source of truth for TS roots: tool/core/repo.ts TYPESCRIPT_DIRS.
const TYPESCRIPT_FILES = ["test/**/*.ts", "tool/**/*.ts"];

export default tseslint.config(
  {
    ignores: [
      "node_modules/**",
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
  {
    files: TYPESCRIPT_FILES,
    ignores: ["test/plugin_sources.ts", "**/*.d.ts"],
    plugins: { jsdoc },
    rules: {
      "jsdoc/require-jsdoc": [
        "error",
        {
          enableFixer: false,
          exemptEmptyConstructors: true,
          require: {
            FunctionDeclaration: true,
            ClassDeclaration: true,
            ClassExpression: true,
            MethodDefinition: true,
            ArrowFunctionExpression: false,
            FunctionExpression: false,
          },
          contexts: [
            "VariableDeclarator > ArrowFunctionExpression",
            "VariableDeclarator > FunctionExpression",
            "FunctionExpression[id]",
            "AssignmentExpression > ArrowFunctionExpression",
            "AssignmentExpression > FunctionExpression",
            "Property > ArrowFunctionExpression",
            "Property > FunctionExpression",
            "PropertyDefinition > ArrowFunctionExpression",
            "PropertyDefinition > FunctionExpression",
            "TSInterfaceDeclaration",
            "TSTypeAliasDeclaration",
          ],
        },
      ],
      "jsdoc/require-description": ["error", { contexts: ["any"], exemptedBy: [] }],
      "jsdoc/require-file-overview": "error",
    },
  },
  eslintConfigPrettier,
);
