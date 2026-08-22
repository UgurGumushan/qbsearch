import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { END_MARKER, START_MARKER } from "../../generate/harden/constants";
import { inspectPlugin } from "../../generate/catalog/index";
import { versionFromSource } from "./plugin_source";
import type { LivePluginContract } from "./types";

export async function inspectLivePlugin(
  path: string,
  sourceOverride?: string,
): Promise<LivePluginContract> {
  const source = sourceOverride ?? (await readFile(path, "utf8"));
  const id = basename(path, ".py");
  const errors: string[] = [];
  let name = "";
  let siteUrl = "";

  try {
    const metadata = await inspectPlugin(path);
    name = metadata.name;
    siteUrl = metadata.site_url;
  } catch (error) {
    errors.push(`metadata: ${error instanceof Error ? error.message : String(error)}`);
  }

  const version = versionFromSource(source);
  if (!version) {
    errors.push("missing or invalid #VERSION: line (qBittorrent requires two numeric parts)");
  }
  if (!/^[ \t]+def\s+search\s*\(/m.test(source)) {
    errors.push("missing qBittorrent search method");
  }
  if (!source.includes(START_MARKER) || !source.includes(END_MARKER)) {
    errors.push("missing generated safety preamble");
  }
  if (siteUrl) {
    try {
      new URL(siteUrl);
    } catch {
      errors.push(`class url is not a valid URL: ${siteUrl}`);
    }
  }

  return {
    id,
    name,
    siteUrl,
    version: version ?? "unknown",
    source,
    errors: [...new Set(errors)],
  };
}
