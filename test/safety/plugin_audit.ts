/**
 * Check engine safety and Python syntax before behavior tests.
 * @file
 */
import { basename } from "node:path";
import { auditPlugin } from "../../tool/checks/harden/audit_plugin";
import { discoverCatalogPlugins } from "../../tool/core/plugins";

/** Check every catalog engine for safety violations and Python syntax errors. */
export async function auditPlugins(): Promise<void> {
  const plugins = await discoverCatalogPlugins();
  for (const path of plugins) {
    const errors = await auditPlugin(path);
    if (errors.length > 0) {
      throw new Error(`${basename(path)}: ${errors.join("; ")}`);
    }
  }
}
