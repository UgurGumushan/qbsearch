/** @deprecated Import from tool/core/repo.ts instead. Thin shim kept for migration. */
export { CATALOG_PATH, FIXTURES_DIR, PLUGIN_DIR, ROOT, TEST_DIR } from "../../tool/core/repo";
import { resolve } from "node:path";
import { TEST_DIR } from "../../tool/core/repo";

export const LIVE_WORKER = resolve(TEST_DIR, "live_plugin.ts");
export const LIVE_SAFETY_SUITE = resolve(TEST_DIR, "live_safety.ts");
