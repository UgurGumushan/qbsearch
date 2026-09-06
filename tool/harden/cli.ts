#!/usr/bin/env bun

/** Compatibility façade and direct entrypoint for the hardening worker. */
export * from "./index";
import { hardenPlugins } from "./command";

if (import.meta.main) {
  const args = Bun.argv.slice(2);
  process.exitCode = await hardenPlugins(args.length > 0 ? args : ["--check"]);
}
