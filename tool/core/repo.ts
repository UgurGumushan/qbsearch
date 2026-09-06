import { resolve } from "node:path";

/** Single source of truth for repository locations. */
export const ROOT = resolve(import.meta.dir, "../..");
export const PLUGIN_DIR = resolve(ROOT, "plugins");
export const ICON_DIR = resolve(ROOT, "icons");
export const CATALOG_PATH = resolve(ROOT, "catalog", "plugins.json");
export const DOCUMENTATION_DIR = resolve(ROOT, "documentation");
export const DOCS_PATH = resolve(DOCUMENTATION_DIR, "PLUGINS.md");
export const CLI_DOCS_PATH = resolve(DOCUMENTATION_DIR, "CLI.md");
export const INSTALL_DIR = resolve(ROOT, "install");
export const SCREENSHOT_PATH = resolve(ROOT, "images", "screenshot.png");
export const WORKING_DIR = resolve(ROOT, "working");
export const UPSTREAM_DIR = resolve(ROOT, "external", "upstream");
export const TEST_DIR = resolve(ROOT, "test");
export const FIXTURES_DIR = resolve(TEST_DIR, "fixtures");
export const PLUGIN_SOURCES_PATH = resolve(TEST_DIR, "plugin_sources.ts");
export const ICONS_MANIFEST_PATH = resolve(WORKING_DIR, "icons-manifest.json");

/**
 * TypeScript source roots owned by the repo command layer.
 * Keep tsconfig.json include, eslint.config.js, and package.json
 * in sync with this list when adding a directory.
 */
export const TYPESCRIPT_DIRS = ["test", "tool"] as const;

export const TYPESCRIPT_GLOBS = TYPESCRIPT_DIRS.map((dir) => `${dir}/**/*.ts`);

export const WEBSITE_GLOBS = ["packages/website/**/*.{ts,tsx}"];
