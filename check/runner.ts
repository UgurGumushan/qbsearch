import { ROOT } from "../scripts/repository";
import type { CheckResult, CheckTask } from "./types";

async function runTask(task: CheckTask): Promise<CheckResult> {
  console.log(`Starting ${task.label}...`);
  try {
    const child = Bun.spawn(task.command, {
      cwd: ROOT,
      stdin: "inherit",
      stdout: "inherit",
      stderr: "inherit",
    });
    const exitCode = await child.exited;
    return { ...task, exitCode };
  } catch (error) {
    console.error(
      `${task.label} could not start: ${error instanceof Error ? error.message : String(error)}`,
    );
    return { ...task, exitCode: 127 };
  }
}

/** Run independent checks concurrently and report every failure. */
export async function runParallel(tasks: CheckTask[]): Promise<number> {
  const results = await Promise.all(tasks.map((task) => runTask(task)));
  const failures = results.filter((result) => result.exitCode !== 0);
  if (failures.length === 0) {
    return 0;
  }

  console.error("\nFailed checks:");
  for (const failure of failures) {
    console.error(`  ${failure.label} (exit code ${failure.exitCode})`);
  }
  return failures[0].exitCode || 1;
}
