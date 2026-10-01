import { CHECK_TASKS } from "./tasks";
import { runParallel } from "../core/run";
import type { CheckScope } from "./types";

function usage(): string {
  return `Usage: bun tool/checks/cli.ts SCOPE

Run independent repository checks in parallel.

Scopes:
  check    Run the test suite and all static checks
  static   Run static and generated-file checks (public command: bun run check -- --fast)
  python   Run Ruff and BasedPyright checks
`;
}

function parseScope(args: string[]): CheckScope | null {
  const scope = args[0] ?? "check";
  if (scope === "--help" || scope === "-h") {
    console.log(usage());
    return null;
  }
  if (args.length !== 1 || !Object.hasOwn(CHECK_TASKS, scope)) {
    throw new Error(`unrecognized check scope: ${scope}`);
  }
  return scope as CheckScope;
}

/** Execute a named repository check scope. */
export async function runChecks(args: string[]): Promise<number> {
  const scope = parseScope(args);
  return scope === null ? 0 : runParallel(CHECK_TASKS[scope]);
}
