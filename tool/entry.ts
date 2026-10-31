#!/usr/bin/env bun
/**
 * Normalize CLI invocation and dispatch the selected maintainer command.
 * @file
 */
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
