import { CHECK_TASKS } from "../checks/tasks";
import { runParallel } from "../core/run";

export type CheckMode = "fast" | "full";
interface CheckArguments {
  mode: CheckMode;
  strict: boolean;
}

function parseArguments(rawArgs: string[]): CheckArguments {
  let mode: CheckMode = "full";
  let strict = false;
  for (const arg of rawArgs) {
    if (arg === "--fast") {
      mode = "fast";
    } else if (arg === "--full") {
      mode = "full";
    } else if (arg === "--strict") {
      strict = true;
    } else {
      throw new Error(`unrecognized argument: ${arg}`);
    }
  }
  return { mode, strict };
}

/** check --fast runs static checks only (hook parity); --full adds bun test. */
export async function runCheckCommand(rawArgs: string[]): Promise<number> {
  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    console.log(`Usage: bun run check [-- --fast|--full|--strict|--help]

Modes:
  --fast   TypeScript, ESLint, Prettier, Python, plugin quality + generated-file audit (pre-commit hook)
  --full   --fast plus the deterministic Bun test suite (default, CI gate)
  --strict In strict mode, metadata warnings become hard failures
`);
    return 0;
  }

  let parsed: CheckArguments;
  try {
    parsed = parseArguments(rawArgs);
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }

  if (parsed.mode === "fast") {
    return runParallel(parsed.strict ? CHECK_TASKS.staticStrict : CHECK_TASKS.static);
  }
  return runParallel(parsed.strict ? CHECK_TASKS.checkStrict : CHECK_TASKS.check);
}
