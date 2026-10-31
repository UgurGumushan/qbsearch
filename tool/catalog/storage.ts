import { readFile } from "node:fs/promises";
import { CATALOG_PATH } from "../core/repo";
import { isRecord } from "../core/guards";
import type { Catalog, CatalogEntry, InstallableCatalogEntry } from "./types";

export async function loadCatalog(path: string = CATALOG_PATH): Promise<Catalog> {
  let source: string;
  try {
    source = await readFile(path, "utf8");
  } catch {
    throw new Error("catalog is missing: " + path);
  }
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch (error) {
    throw new Error(
      "catalog is not valid JSON: " + (error instanceof Error ? error.message : String(error)),
      { cause: error },
    );
  }
  if (!isRecord(value)) {
    throw new TypeError("catalog root must be an object");
  }
  return value as Catalog;
}

export function catalogEntries(catalog: Catalog): CatalogEntry[] {
  const entries = catalog.plugins;
  if (!Array.isArray(entries)) {
    throw new TypeError("catalog.plugins must be an array");
  }
  const typedEntries: CatalogEntry[] = [];
  for (const entry of entries) {
    if (!isRecord(entry)) {
      throw new TypeError("every catalog.plugins entry must be an object");
    }
    typedEntries.push(entry);
  }
  return typedEntries;
}

/** Return the catalog fields required to include every plugin in a release. */
export function installableCatalogEntries(catalog: Catalog): InstallableCatalogEntry[] {
  return catalogEntries(catalog).map((entry, index) => {
    if (typeof entry.id !== "string" || entry.id.length === 0) {
      throw new TypeError(`catalog.plugins entry ${index} has an invalid id`);
    }
    if (typeof entry.icon !== "string" || entry.icon.length === 0) {
      throw new TypeError(`${entry.id} has an invalid icon`);
    }
    return { id: entry.id, icon: entry.icon };
  });
}
