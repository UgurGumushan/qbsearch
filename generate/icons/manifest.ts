import { readFile } from "node:fs/promises";
import { MANIFEST } from "./constants";
import type { Manifest, ManifestEntry } from "./types";
import { isRecord } from "../../scripts/common/guards";

function parseManifestEntry(value: unknown): ManifestEntry | null {
  if (!isRecord(value)) {
    return null;
  }
  if (
    (typeof value.url !== "string" && value.url !== null) ||
    typeof value.host !== "string" ||
    typeof value.ico !== "string" ||
    typeof value.ok !== "boolean" ||
    (typeof value.error !== "string" && value.error !== null) ||
    (typeof value.source !== "string" && value.source !== null)
  ) {
    return null;
  }
  return {
    url: value.url,
    host: value.host,
    ico: value.ico,
    ok: value.ok,
    error: value.error,
    source: value.source,
  };
}

/** Load the previous icon manifest, ignoring malformed entries. */
export async function readPreviousManifest(): Promise<Manifest> {
  try {
    const value: unknown = JSON.parse(await readFile(MANIFEST, "utf8"));
    if (!isRecord(value)) {
      return {};
    }
    const manifest: Manifest = {};
    for (const [stem, rawEntry] of Object.entries(value)) {
      const entry = parseManifestEntry(rawEntry);
      if (entry !== null) {
        manifest[stem] = entry;
      }
    }
    return manifest;
  } catch {
    return {};
  }
}
