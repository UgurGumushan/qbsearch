#!/usr/bin/env bun

/** Direct entrypoint and compatibility façade for repository checks. */
export * from "./index";
import { runChecks } from "./command";

if (import.meta.main) {
  try {
    process.exitCode = await runChecks(Bun.argv.slice(2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
