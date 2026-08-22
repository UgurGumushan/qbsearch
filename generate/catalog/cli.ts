#!/usr/bin/env bun

/** Direct entrypoint for catalog generation. */
export { generatePluginCatalog } from "./command";
import { generatePluginCatalog } from "./command";

if (import.meta.main) {
  try {
    process.exitCode = await generatePluginCatalog(Bun.argv.slice(2));
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
