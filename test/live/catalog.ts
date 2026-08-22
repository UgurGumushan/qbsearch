import { CATALOG_PATH } from "../support/paths";
import { catalogEntries, loadCatalog } from "../../generate/catalog";

export interface LiveCatalogEntry {
  id: string;
  category: string;
  defaultQuery: string;
  status: string;
}

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
