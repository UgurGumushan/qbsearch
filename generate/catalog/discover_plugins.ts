import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { PLUGIN_DIR } from "../../scripts/repository";

/** Find installable Python engines in deterministic filename order. */
export async function discoverPlugins(): Promise<string[]> {
  const entries = await readdir(PLUGIN_DIR, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".py"))
    .map((entry) => join(PLUGIN_DIR, entry.name))
    .sort();
}
