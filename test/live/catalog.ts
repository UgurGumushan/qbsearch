/**
 * Project catalog metadata into live-test selection inputs.
 * @file
 */
import { CATALOG_PATH } from "../../tool/core/repo";
import { catalogEntries, loadCatalog } from "../../tool/catalog/storage";

/** Catalog fields needed to select live probes and their public search queries. */
export interface LiveCatalogEntry {
  id: string;
  category: string;
  defaultQuery: string;
  status: string;
}

/** Validate and project catalog entries into the live runner input shape. */
export async function loadLiveCatalog(path = CATALOG_PATH): Promise<LiveCatalogEntry[]> {
  const catalog = await loadCatalog(path);
  return catalogEntries(catalog).map((entry, index) => {
    if (!entry.id || !entry.category || !entry.default_query || !entry.status) {
      throw new Error(`catalog.plugins entry ${index} has invalid live-test metadata`);
    }
    return {
      id: entry.id,
      category: entry.category,
      defaultQuery: entry.default_query,
      status: entry.status,
    };
  });
}
