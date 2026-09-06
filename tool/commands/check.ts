import { CHECK_TASKS } from "../checks/tasks";
import { runParallel } from "../core/run";

export type CheckMode = "fast" | "full";

/** check --fast runs static checks only (hook parity); --full adds bun test. */
export async function runCheckCommand(rawArgs: string[]): Promise<number> {
  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    console.log(`Usage: bun run check [-- --fast|--full|--help]

Modes:
  --fast   TypeScript, ESLint, Prettier, Python checks + generated-file audit (pre-commit hook)
  --full   --fast plus the deterministic Bun test suite (default, CI gate)
`);
    return 0;
  }
  const mode: CheckMode = rawArgs.includes("--fast") ? "fast" : "full";
  if (mode === "fast") {
    return runParallel(CHECK_TASKS.static);
  }
  return runParallel(CHECK_TASKS.check);
}
