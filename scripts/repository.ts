import { resolve } from "node:path";

/** Absolute paths shared by repository maintenance workers. */
export const ROOT = resolve(import.meta.dir, "..");
export const PLUGIN_DIR = resolve(ROOT, "plugins");
export const ICON_DIR = resolve(ROOT, "icons");
export const CATALOG_PATH = resolve(ROOT, "catalog", "plugins.json");
export const DOCUMENTATION_DIR = resolve(ROOT, "documentation");
export const DOCS_PATH = resolve(DOCUMENTATION_DIR, "PLUGINS.md");
export const INSTALL_DIR = resolve(ROOT, "install");
export const SCREENSHOT_PATH = resolve(ROOT, "images", "screenshot.png");
export const WORKING_DIR = resolve(ROOT, "working");
export const UPSTREAM_DIR = resolve(ROOT, "external", "upstream");
