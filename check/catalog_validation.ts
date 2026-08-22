import { readFile } from "node:fs/promises";
import { basename, relative, resolve } from "node:path";
import { ROOT } from "../scripts/repository";
import { VALID_CATEGORIES, VALID_STATUSES } from "../generate/catalog/constants";
import { discoverPlugins } from "../generate/catalog/discover_plugins";
import { inspectPlugin } from "../generate/catalog/inspect_plugin";
import { catalogEntries } from "../generate/catalog/storage";
import type { Catalog, CatalogEntry } from "../generate/catalog/types";

function pythonRepr(value: unknown): string {
  if (typeof value === "string") {
    return `'${value.replaceAll("'", "\\'")}'`;
  }
  if (value === null) {
    return "None";
  }
  if (typeof value === "boolean") {
    return value ? "True" : "False";
  }
  if (typeof value === "number" || typeof value === "bigint") {
    return String(value);
  }
  if (value === undefined) {
    return "None";
  }
  return JSON.stringify(value);
}

/** Validate catalog schema, plugin parity, metadata, and icon files. */
export async function validateCatalog(catalog: Catalog): Promise<string[]> {
  const errors: string[] = [];
  if (catalog.schema_version !== 1) {
    errors.push("schema_version must be 1");
  }

  let entries: CatalogEntry[];
  try {
    entries = catalogEntries(catalog);
  } catch (error) {
    return [error instanceof Error ? error.message : String(error)];
  }

  const seen = new Set<string>();
  const paths = new Map<string, string>();
  for (const path of await discoverPlugins()) {
    paths.set(basename(path, ".py"), path);
  }

  for (const entry of entries) {
    const stem = entry.id;
    if (typeof stem !== "string" || stem.length === 0) {
      errors.push("plugin entry has an invalid id");
      continue;
    }
    if (seen.has(stem)) {
      errors.push("duplicate catalog id: " + stem);
    }
    seen.add(stem);

    const required = ["name", "site_url", "category", "default_query", "status", "icon"];
    const missing = required.filter((field) => !Object.hasOwn(entry, field));
    if (missing.length > 0) {
      errors.push(stem + " is missing: " + missing.join(", "));
      continue;
    }
    const pluginPath = paths.get(stem);
    if (pluginPath === undefined) {
      errors.push(stem + " is in the catalog but not in plugins/");
      continue;
    }
    if (typeof entry.category !== "string" || !VALID_CATEGORIES.has(entry.category)) {
      errors.push(stem + " has invalid category: " + pythonRepr(entry.category));
    }
    if (typeof entry.status !== "string" || !VALID_STATUSES.has(entry.status)) {
      errors.push(stem + " has invalid status: " + pythonRepr(entry.status));
    }
    if (typeof entry.default_query !== "string" || entry.default_query.trim().length === 0) {
      errors.push(stem + " must have a non-empty default_query");
    }
    if (entry.icon !== `icons/${stem}.ico`) {
      errors.push(stem + " icon must be icons/" + stem + ".ico");
    }
    const requiresAuth = Object.hasOwn(entry, "requires_auth") ? entry.requires_auth : false;
    if (typeof requiresAuth !== "boolean") {
      errors.push(stem + " requires_auth must be boolean");
    }
    const icon = resolve(ROOT, entry.icon);
    try {
      await readFile(icon);
    } catch {
      errors.push(stem + " is missing icon: " + relative(ROOT, icon));
    }

    try {
      const sourceMetadata = await inspectPlugin(pluginPath);
      if (entry.name !== sourceMetadata.name) {
        errors.push(stem + " catalog name does not match plugin class");
      }
      if (entry.site_url !== sourceMetadata.site_url) {
        errors.push(stem + " catalog site_url does not match plugin class");
      }
    } catch (error) {
      errors.push(
        stem +
          " metadata cannot be inspected: " +
          (error instanceof Error ? error.message : String(error)),
      );
    }
  }

  const missing = [...paths.keys()].filter((stem) => !seen.has(stem)).sort();
  if (missing.length > 0) {
    errors.push("plugins missing from catalog: " + missing.join(", "));
  }
  return errors;
}
