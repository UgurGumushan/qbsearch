import { extname, join, resolve } from "node:path";
import { readdir, stat } from "node:fs/promises";
import { DOCUMENTATION_DIR, INSTALL_DIR, ROOT, SCREENSHOT_PATH } from "./constants";
import type { CatalogEntry } from "./types";

async function isFile(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isFile();
  } catch {
    return false;
  }
}

async function supportFiles(): Promise<string[]> {
  const pluginDirectory = resolve(ROOT, "plugins");
  const entries = await readdir(pluginDirectory, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && extname(entry.name) === ".json")
    .map((entry) => join(pluginDirectory, entry.name))
    .sort();
}

/** Resolve the repository files included in a release archive. */
export async function archiveSources(catalogEntries: CatalogEntry[]): Promise<string[]> {
  const files = [
    resolve(ROOT, "README.md"),
    resolve(DOCUMENTATION_DIR, "INSTALL.md"),
    resolve(DOCUMENTATION_DIR, "PLUGINS.md"),
    resolve(ROOT, "CONTRIBUTING.md"),
    resolve(DOCUMENTATION_DIR, "CHANGELOG.md"),
    resolve(DOCUMENTATION_DIR, "ATTRIBUTIONS.md"),
    resolve(ROOT, "LICENSE.md"),
    SCREENSHOT_PATH,
    resolve(ROOT, "catalog", "plugins.json"),
    resolve(INSTALL_DIR, "macos.sh"),
    resolve(INSTALL_DIR, "linux.sh"),
    resolve(INSTALL_DIR, "windows.ps1"),
  ];
  for (const entry of catalogEntries) {
    files.push(resolve(ROOT, "plugins", `${entry.id}.py`));
    files.push(resolve(ROOT, entry.icon));
  }
  files.push(...(await supportFiles()));
  const existingFiles: string[] = [];
  for (const file of files) {
    if (await isFile(file)) {
      existingFiles.push(file);
    }
  }
  return existingFiles;
}
