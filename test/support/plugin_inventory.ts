import { basename } from "node:path";
import { catalogEntries, discoverPlugins, loadCatalog } from "../../generate/catalog/index";
import { CATALOG_PATH } from "./paths";

/** Return plugin files only when the generated catalog and disk agree. */
export async function discoverCatalogPlugins(): Promise<string[]> {
  const [paths, catalog] = await Promise.all([discoverPlugins(), loadCatalog(CATALOG_PATH)]);
  const catalogIds = catalogEntries(catalog).map((entry, index) => {
    if (typeof entry.id !== "string" || !entry.id) {
      throw new Error(`catalog.plugins entry ${index} has an invalid id`);
    }
    return entry.id;
  });
  const pluginIds = paths.map((path) => basename(path, ".py"));
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
