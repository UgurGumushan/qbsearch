import { ROOT } from "./repository";

export interface CommandResult {
  code: number;
  output: string;
}

export type TimedCommandResult = CommandResult & {
  elapsed: number;
  timedOut: boolean;
};

export interface RunCommandOptions {
  cwd?: string;
  timeoutSeconds?: number | null;
}

/** Resolve the Python executable used by repository checks and workers. */
export function pythonCommand(): string[] {
  const configured = process.env.QBSEARCH_PYTHON;
  if (configured) {
    return [configured];
  }

  const candidates =
    process.platform === "win32"
      ? [["py", "-3"], ["python"], ["python3"]]
      : [["python3"], ["python"]];
  for (const candidate of candidates) {
    if (Bun.which(candidate[0])) {
      return candidate;
    }
  }

  throw new Error("Python 3 was not found. Install Python 3.9 or newer, or set QBSEARCH_PYTHON.");
}

/** Run a repository command with inherited standard streams. */
export async function runCommand(command: string[], label: string): Promise<number> {
  try {
    const child = Bun.spawn(command, {
      cwd: ROOT,
      stdin: "inherit",
      stdout: "inherit",
      stderr: "inherit",
    });
    const exitCode = await child.exited;
    if (exitCode !== 0) {
      console.error(`${label} failed with exit code ${exitCode}.`);
    }
    return exitCode;
  } catch (error) {
    console.error(
      `${label} could not start: ${error instanceof Error ? error.message : String(error)}`,
    );
    return 127;
  }
}

async function commandOutput(child: Bun.Subprocess<"ignore", "pipe", "pipe">): Promise<string> {
  const stdout = new Response(child.stdout).text();
  const stderr = new Response(child.stderr).text();
  const [out, err] = await Promise.all([stdout, stderr]);
  return [out, err]
    .filter(Boolean)
    .map((part) => part.trim())
    .filter(Boolean)
    .join("\n");
}

/** Run a command while capturing output and enforcing an optional timeout. */
export async function runCapturedCommand(
  command: string[],
  options: RunCommandOptions = {},
): Promise<TimedCommandResult> {
  const started = performance.now();
  const timeoutSeconds = options.timeoutSeconds ?? null;

  try {
    const child = Bun.spawn(command, {
      cwd: options.cwd ?? ROOT,
      stdout: "pipe",
      stderr: "pipe",
    });
    let timer: ReturnType<typeof setTimeout> | undefined;
    const exit = await new Promise<{ code: number; timedOut: boolean }>((resolveExit) => {
      let settled = false;
      const finish = (result: { code: number; timedOut: boolean }): void => {
        if (settled) {
          return;
        }
        settled = true;
        if (timer !== undefined) {
          clearTimeout(timer);
        }
        resolveExit(result);
      };

      void child.exited.then((code) => {
        finish({ code, timedOut: false });
      });
      if (timeoutSeconds !== null) {
        timer = setTimeout(
          () => {
            child.kill();
            finish({ code: -1, timedOut: true });
          },
          Math.max(0, timeoutSeconds * 1000),
        );
      }
    });
    const output = await commandOutput(child);

    return {
      code: exit.code,
      output: exit.timedOut
        ? `timed out after ${timeoutSeconds}s${output ? `\n${output}` : ""}`
        : output,
      elapsed: (performance.now() - started) / 1000,
      timedOut: exit.timedOut,
    };
  } catch (error) {
    return {
      code: 127,
      output: `could not start process: ${error instanceof Error ? error.message : String(error)}`,
      elapsed: (performance.now() - started) / 1000,
      timedOut: false,
    };
  }
}

/** Run Python with the repository's configured interpreter. */
export async function runPython(args: string[], label: string): Promise<number> {
  return runCommand([...pythonCommand(), ...args], label);
}

/** Run Python while capturing output for deterministic tests. */
export function runPythonCaptured(args: string[]): Promise<TimedCommandResult> {
  return runCapturedCommand([...pythonCommand(), ...args]);
}
