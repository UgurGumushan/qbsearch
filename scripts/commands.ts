#!/usr/bin/env bun

/** Bun entrypoint for repository maintenance commands. */
import { runCommandLine } from "./command/cli";

if (import.meta.main) {
  try {
    process.exitCode = await runCommandLine(Bun.argv.slice(2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
