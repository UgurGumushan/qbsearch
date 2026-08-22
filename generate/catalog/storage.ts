import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { CATALOG_PATH, ROOT } from "../../scripts/repository";
import { isRecord } from "../../scripts/common/guards";
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

export async function writeCatalog(catalog: Catalog, path: string = CATALOG_PATH): Promise<void> {
  await mkdir(resolve(path, ".."), { recursive: true });
  await writeFile(path, JSON.stringify(catalog, null, 2) + "\n", "utf8");
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

export async function licenseMap(): Promise<Record<string, string>> {
  const licenseFile = resolve(ROOT, "LICENSE.md");
  let source: string;
  try {
    source = await readFile(licenseFile, "utf8");
  } catch {
    return {};
  }
  const licenses: Record<string, string> = {};
  const pattern = /^\| \[([A-Za-z0-9_]+)\.py\]\(plugins\/[^)]+\) \| ([^|]+) \|$/gm;
  for (const match of source.matchAll(pattern)) {
    licenses[match[1]] = match[2].trim();
  }
  return licenses;
}
