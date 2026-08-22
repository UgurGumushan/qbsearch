import {
  runCapturedCommand,
  runPythonCaptured,
  type CommandResult,
  type TimedCommandResult,
} from "../../scripts/process";

export type { CommandResult, TimedCommandResult } from "../../scripts/process";
export { pythonCommand } from "../../scripts/process";

export function runCommand(
  command: string[],
  options: { cwd?: string; timeoutSeconds?: number | null } = {},
): Promise<TimedCommandResult> {
  return runCapturedCommand(command, options);
}

export async function runPython(args: string[]): Promise<CommandResult> {
  const result = await runPythonCaptured(args);
  return { code: result.code, output: result.output };
}

export function assertPassed(label: string, result: CommandResult): void {
  if (result.code !== 0) {
    throw new Error(`${label} failed with exit code ${result.code}.\n${result.output}`);
  }
}
