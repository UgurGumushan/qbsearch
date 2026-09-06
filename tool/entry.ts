#!/usr/bin/env bun
/** Unified entrypoint for repository maintenance commands. */
import { runCommandLine } from "./cli";

if (import.meta.main) {
  try {
    process.exitCode = await runCommandLine(Bun.argv.slice(2));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
