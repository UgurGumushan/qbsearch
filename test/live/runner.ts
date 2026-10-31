/**
 * Launch isolated probe workers with bounded concurrency and timeouts.
 * @file
 */
import { availableParallelism } from "node:os";
import { basename, resolve } from "node:path";
import { PLUGIN_DIR, TEST_DIR } from "../../tool/core/repo";
import { runCapturedCommand, type TimedCommandResult } from "../../tool/core/run";

const LIVE_WORKER = resolve(TEST_DIR, "live_plugin.ts");
const LIVE_SAFETY_SUITE = resolve(TEST_DIR, "live_safety.ts");

/** Worker outcome with elapsed time, human-readable detail, and captured output. */
export interface LiveTestResult {
  name: string;
  passed: boolean;
  elapsed: number;
  output: string;
  detail: string;
}

/** Choose at least one worker CPU even when platform introspection fails. */
export function logicalCpuCount(): number {
  try {
    return Math.max(1, availableParallelism());
  } catch {
    return Math.max(1, navigator.hardwareConcurrency || 1);
  }
}

/** Convert a captured process result into the live runner reporting shape. */
function resultFromCommand(name: string, result: TimedCommandResult): LiveTestResult {
  return {
    name,
    passed: !result.timedOut && result.code === 0,
    elapsed: result.elapsed,
    output: result.output,
    detail: "",
  };
}

/** Run a Bun worker with captured output and a wall-clock timeout. */
export async function runBunScript(
  path: string,
  args: string[],
  timeout: number,
): Promise<LiveTestResult> {
  const result = await runCapturedCommand([process.execPath, path, ...args], {
    timeoutSeconds: timeout,
  });
  return resultFromCommand("TypeScript live helpers", result);
}

/** Launch one plugin worker with its query and installability or live mode. */
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
    await runCapturedCommand(command, { timeoutSeconds: timeout }),
  );
  result.detail = result.output.split(/\r?\n/).find((line) => line.startsWith("LIVE ")) ?? "";
  return result;
}

/** Run the isolated transport safety suite within the requested timeout. */
export async function runLiveSafety(timeout: number): Promise<LiveTestResult> {
  return runBunScript(LIVE_SAFETY_SUITE, [], timeout);
}

/** Map inputs through a bounded worker pool while retaining input order. */
export async function mapConcurrent<T, R>(
  items: T[],
  workers: number,
  task: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  /** Claim the next unprocessed input until the shared queue is exhausted. */
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

/** Resolve a catalog engine ID to its standalone Python file. */
export function pluginPath(id: string): string {
  return resolve(PLUGIN_DIR, `${id}.py`);
}

/** Print captured worker diagnostics only for failed probes. */
export function printFailureDetails(result: LiveTestResult): void {
  if (result.passed || !result.output) {
    return;
  }
  console.log(`\n--- ${result.name} test output ---`);
  console.log(result.output);
}
