#!/usr/bin/env bun

/** Compatibility façade and direct entrypoint for icon generation. */
export * from "./index";
import { makeIcons } from "./command";

if (import.meta.main) {
  try {
    process.exitCode = await makeIcons(Bun.argv.slice(2));
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}
