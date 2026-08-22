#!/usr/bin/env bun

/** Compatibility façade and direct entrypoint for upstream imports. */
export * from "./index";
import { importUpstreamPlugins } from "./command";

if (import.meta.main) {
  try {
    process.exitCode = await importUpstreamPlugins(Bun.argv.slice(2));
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
