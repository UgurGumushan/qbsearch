import { relative, sep } from "node:path";
import { ROOT } from "./constants";
import type { CatalogEntry } from "./types";

export function archivePath(prefix: string, path: string): string {
  return `${prefix}/${relative(ROOT, path).split(sep).join("/")}`;
}

export function manifestText(version: string, entries: CatalogEntry[]): string {
  return (
    JSON.stringify(
      {
        version,
        plugin_count: entries.length,
        plugins: entries.map((entry) => entry.id),
        installers: ["install/macos.sh", "install/linux.sh", "install/windows.ps1"],
      },
      null,
      2,
    ) + "\n"
  );
}
