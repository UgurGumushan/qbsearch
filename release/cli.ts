#!/usr/bin/env bun

/** Direct entrypoint for release archive generation. */
export { buildRelease } from "./index";
export type { CatalogEntry, ParsedArguments } from "./index";
import { buildRelease } from "./command";
import { normalizeReleaseArguments } from "./command_arguments";

if (import.meta.main) {
  process.exitCode = await buildRelease(normalizeReleaseArguments(Bun.argv.slice(2)));
}
