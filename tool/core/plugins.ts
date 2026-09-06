import { readdir, readFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { CATALOG_PATH, PLUGIN_DIR } from "./repo";
import { metadataFromSource } from "./python-parse";

export interface CatalogEntry {
  id: string;
  name: string;
  site_url: string;
  category: string;
  default_query: string;
  status: string;
  icon: string;
  requires_auth?: boolean;
  [key: string]: unknown;
}

/** Find installable Python engines in deterministic filename order. */
export async function discoverPlugins(): Promise<string[]> {
  const entries = await readdir(PLUGIN_DIR, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".py"))
    .map((entry) => join(PLUGIN_DIR, entry.name))
    .sort();
}

export function pluginId(path: string): string {
  return basename(path, ".py");
}

async function loadCatalogJson(): Promise<{ plugins: CatalogEntry[] }> {
  const raw = await readFile(CATALOG_PATH, "utf8");
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null || !("plugins" in parsed)) {
    throw new Error("catalog must have a plugins array");
  }
  const plugins: unknown = parsed.plugins;
  if (!Array.isArray(plugins)) {
    throw new Error("catalog.plugins must be an array");
  }
  return { plugins: plugins as CatalogEntry[] };
}

export async function loadCatalogEntries(): Promise<CatalogEntry[]> {
  return (await loadCatalogJson()).plugins;
}

/**
 * Return plugin files only when disk and catalog agree.
 * Throws with actionable detail otherwise.
 */
export async function discoverCatalogPlugins(): Promise<string[]> {
  const [paths, entries] = await Promise.all([discoverPlugins(), loadCatalogEntries()]);
  const catalogIds = entries.map((entry, index) => {
    if (typeof entry.id !== "string" || !entry.id) {
      throw new Error(`catalog.plugins entry ${index} has an invalid id`);
    }
    return entry.id;
  });
  const pluginIds = paths.map(pluginId);
  const catalogIdSet = new Set(catalogIds);
  const pluginIdSet = new Set(pluginIds);
  const missingFromCatalog = pluginIds.filter((id) => !catalogIdSet.has(id));
  const missingFromDisk = catalogIds.filter((id) => !pluginIdSet.has(id));
  if (missingFromCatalog.length > 0 || missingFromDisk.length > 0) {
    const details = [
      missingFromCatalog.length > 0 ? `missing from catalog: ${missingFromCatalog.join(", ")}` : "",
      missingFromDisk.length > 0 ? `missing from plugins/: ${missingFromDisk.join(", ")}` : "",
    ]
      .filter(Boolean)
      .join("; ");
    throw new Error(`plugin inventory does not match the catalog (${details})`);
  }
  return paths;
}

export async function readPluginSource(path: string): Promise<string> {
  return readFile(path, "utf8");
}

/** Inspect name/url metadata for one plugin file. */
export async function inspectPluginFile(path: string): Promise<{ name: string; site_url: string }> {
  return metadataFromSource(await readPluginSource(path), pluginId(path));
}
