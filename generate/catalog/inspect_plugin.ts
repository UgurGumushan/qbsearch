import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { assignmentValue, classBodies, topLevelConstants, CLASS_ATTRIBUTES } from "./python_source";
import type { PluginMetadata } from "./types";

/** Read the qBittorrent metadata fields from one standalone engine. */
export async function inspectPlugin(path: string): Promise<PluginMetadata> {
  const source = await readFile(path).catch((error: unknown) => {
    throw new Error(error instanceof Error ? error.message : String(error));
  });
  const lines = source.toString().split(/\r?\n/);
  const constants = topLevelConstants(lines);
  const classes = classBodies(lines);
  const stem = basename(path, ".py");
  let className = classes.has(stem) ? stem : null;

  if (className === null) {
    for (const line of lines) {
      if (/^\s/.test(line)) {
        continue;
      }
      const alias = /^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*$/.exec(
        line,
      );
      if (alias?.[1] === stem && alias[2] && classes.has(alias[2])) {
        className = alias[2];
        break;
      }
    }
  }
  if (className === null) {
    throw new Error("could not find the qBittorrent engine class");
  }

  const attributes: Record<string, string> = {};
  const classBody = classes.get(className);
  for (const line of classBody?.lines ?? []) {
    if (!classBody || !line.startsWith(classBody.indent)) {
      continue;
    }
    const unindented = line.slice(classBody.indent.length);
    if (/^[ \t]/.test(unindented)) {
      continue;
    }
    const match = unindented.match(CLASS_ATTRIBUTES);
    if (!match || (match[1] !== "name" && match[1] !== "url")) {
      continue;
    }
    const value = assignmentValue(match, constants);
    if (value !== null) {
      attributes[match[1]] = value;
    }
  }
  const missing = ["name", "url"].filter((attribute) => !(attribute in attributes));
  if (missing.length > 0) {
    throw new Error("missing class attribute(s): " + missing.join(", "));
  }
  return { name: attributes.name, site_url: attributes.url };
}
