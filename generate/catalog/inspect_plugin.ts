import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { metadataFromSource } from "../../tool/core/python-parse";
import type { PluginMetadata } from "./types";

/** Read the qBittorrent metadata fields from one standalone engine. */
export async function inspectPlugin(path: string): Promise<PluginMetadata> {
  const source = await readFile(path, "utf8").catch((error: unknown) => {
    throw new Error(error instanceof Error ? error.message : String(error));
  });
  return metadataFromSource(source, basename(path, ".py"));
}
