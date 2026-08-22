import { basename } from "node:path";
import { CATEGORY_HINTS } from "./constants";
import { discoverPlugins } from "./discover_plugins";
import { inspectPlugin } from "./inspect_plugin";
import { catalogEntries, licenseMap } from "./storage";
import type { Catalog } from "./types";

function categoryFor(stem: string): string {
  for (const [category, stems] of Object.entries(CATEGORY_HINTS)) {
    if (stems.has(stem)) {
      return category;
    }
  }
  return "general";
}

export async function bootstrapCatalog(): Promise<Catalog> {
  const [licenses, paths] = await Promise.all([licenseMap(), discoverPlugins()]);
  const entries = [];
  for (const path of paths) {
    const id = basename(path, ".py");
    const metadata = await inspectPlugin(path);
    entries.push({
      id,
      name: metadata.name,
      site_url: metadata.site_url,
      category: categoryFor(id),
      default_query: "ubuntu",
      status: "active",
      icon: `icons/${id}.ico`,
      requires_auth: false,
      source_url: null,
      license: licenses[id] ?? null,
      notes: "",
    });
  }
  return { schema_version: 1, plugins: entries };
}

export async function refreshCatalog(catalog: Catalog): Promise<Catalog> {
  const licenses = await licenseMap();
  for (const entry of catalogEntries(catalog)) {
    const pluginId = entry.id;
    entry.license ??= licenses[pluginId] ?? null;
  }
  return catalog;
}
