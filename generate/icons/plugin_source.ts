import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { PLUGIN_DIR, RE_CONST, RE_URL_ATTR, RE_URL_NAME } from "./constants";

export function extractUrl(source: string): string | null {
  const direct = RE_URL_ATTR.exec(source);
  if (direct?.[1]) {
    return direct[1];
  }

  const reference = RE_URL_NAME.exec(source);
  if (!reference?.[1]) {
    return null;
  }
  for (const constant of source.matchAll(RE_CONST)) {
    if (constant[1] === reference[1]) {
      return constant.slice(2, 3).at(0) ?? null;
    }
  }
  return null;
}

export async function discoverPlugins(): Promise<string[]> {
  const entries = await readdir(PLUGIN_DIR, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".py"))
    .map((entry) => join(PLUGIN_DIR, entry.name))
    .sort();
}

export function hostName(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}
