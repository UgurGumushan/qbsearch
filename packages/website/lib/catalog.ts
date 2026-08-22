import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "./catalog-shared";

export { categoryLabel, pluginSourceUrl, RELEASES_URL, REPOSITORY_URL } from "./catalog-shared";
export type { Plugin, PluginCategory, PluginStatus } from "./catalog-shared";

type Catalog = {
  schema_version: number;
  plugins: Plugin[];
};

const catalogPath = resolve(process.cwd(), "../../catalog/plugins.json");
let catalogPromise: Promise<Plugin[]> | undefined;

/** Read the repository catalog once per server process/build. */
export function getCatalog(): Promise<Plugin[]> {
  catalogPromise ??= readFile(catalogPath, "utf8").then((source) => {
    const catalog = JSON.parse(source) as Catalog;
    return catalog.plugins;
  });
  return catalogPromise;
}
