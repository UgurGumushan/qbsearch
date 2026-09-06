/** @deprecated Import from tool/core/run.ts instead. Thin shim kept for migration. */
export { assertPassed, pythonCommand } from "../../tool/core/run";
export type { CommandResult, TimedCommandResult } from "../../tool/core/run";
import { runCapturedCommand, runPythonCaptured, type CommandResult } from "../../tool/core/run";

export function runCommand(
  command: string[],
  options: { cwd?: string; timeoutSeconds?: number | null } = {},
) {
  return runCapturedCommand(command, options);
}

export async function runPython(args: string[]): Promise<CommandResult> {
  const result = await runPythonCaptured(args);
  return { code: result.code, output: result.output };
}
