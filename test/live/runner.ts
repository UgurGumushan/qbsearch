import { availableParallelism } from "node:os";
import { basename, resolve } from "node:path";
import { LIVE_SAFETY_SUITE, LIVE_WORKER, PLUGIN_DIR } from "../support/paths";
import { runCommand, type TimedCommandResult } from "../support/process";

export interface LiveTestResult {
  name: string;
  passed: boolean;
  elapsed: number;
  output: string;
  detail: string;
}

export function logicalCpuCount(): number {
  try {
    return Math.max(1, availableParallelism());
  } catch {
    return Math.max(1, navigator.hardwareConcurrency || 1);
  }
}

function resultFromCommand(name: string, result: TimedCommandResult): LiveTestResult {
  return {
    name,
    passed: !result.timedOut && result.code === 0,
    elapsed: result.elapsed,
    output: result.output,
    detail: "",
  };
}

export async function runBunScript(
  path: string,
  args: string[],
  timeout: number,
): Promise<LiveTestResult> {
  const result = await runCommand([process.execPath, path, ...args], {
    timeoutSeconds: timeout,
  });
  return resultFromCommand("TypeScript live helpers", result);
}

export async function runPlugin(
  path: string,
  timeout: number,
  live: boolean,
  query: string,
  category: string,
  allowEmpty: boolean,
): Promise<LiveTestResult> {
  const command = [process.execPath, LIVE_WORKER, path];
  if (live) {
    command.push("--query", query, "--category", category);
    if (allowEmpty) {
      command.push("--allow-empty");
    }
  } else {
    command.push("--install-only");
  }

  const result = resultFromCommand(
    basename(path, ".py"),
    await runCommand(command, { timeoutSeconds: timeout }),
  );
  result.detail = result.output.split(/\r?\n/).find((line) => line.startsWith("LIVE ")) ?? "";
  return result;
}

export async function runLiveSafety(timeout: number): Promise<LiveTestResult> {
  return runBunScript(LIVE_SAFETY_SUITE, [], timeout);
}

export async function mapConcurrent<T, R>(
  items: T[],
  workers: number,
  task: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  async function worker(): Promise<void> {
    for (;;) {
      const index = next;
      next += 1;
      if (index >= items.length) {
        return;
      }
      results[index] = await task(items[index]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(workers, items.length) }, () => worker()));
  return results;
}

export function pluginPath(id: string): string {
  return resolve(PLUGIN_DIR, `${id}.py`);
}

export function printFailureDetails(result: LiveTestResult): void {
  if (result.passed || !result.output) {
    return;
  }
  console.log(`\n--- ${result.name} test output ---`);
  console.log(result.output);
}
