import { resolve } from "node:path";
import { CATALOG_PATH, PLUGIN_DIR, ROOT } from "../../scripts/repository";

export { CATALOG_PATH, PLUGIN_DIR, ROOT };

export const TEST_DIR = resolve(ROOT, "test");
export const FIXTURES_DIR = resolve(TEST_DIR, "fixtures");
export const LIVE_WORKER = resolve(TEST_DIR, "live_plugin.ts");
export const LIVE_SAFETY_SUITE = resolve(TEST_DIR, "live_safety.ts");
