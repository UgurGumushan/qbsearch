import { basename } from "node:path";
import { auditPlugin } from "../../check/harden/audit_plugin";
import { discoverCatalogPlugins } from "../support/plugin_inventory";

export async function auditPlugins(): Promise<void> {
  const plugins = await discoverCatalogPlugins();
  for (const path of plugins) {
    const errors = await auditPlugin(path);
    if (errors.length > 0) {
      throw new Error(`${basename(path)}: ${errors.join("; ")}`);
    }
  }
}
