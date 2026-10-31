/**
 * Define the static, generated, and test tasks shared by hooks and CI.
 * @file
 */
import type { CheckTask } from "../core/run";

/** Select the deterministic gate breadth and metadata-warning policy. */
export interface CheckOptions {
  mode: "fast" | "full";
  strict: boolean;
}

/** Flat task list shared by local hooks and CI; every checker runs once per gate. */
export function checkTasks({ mode, strict }: CheckOptions): CheckTask[] {
  const bun = process.execPath;
  const tasks: CheckTask[] = [
    { label: "TypeScript", command: [bun, "run", "typecheck"] },
    { label: "ESLint", command: [bun, "run", "lint"] },
    { label: "Prettier", command: [bun, "run", "format:check"] },
    { label: "Ruff lint", command: ["ruff", "check", "."] },
    { label: "Plugin documentation", command: [bun, "tool/checks/python_documentation.ts"] },
    { label: "Ruff format", command: ["ruff", "format", "--check", "."] },
    { label: "BasedPyright", command: ["basedpyright"] },
    { label: "Plugin quality", command: [bun, "tool/checks/plugin_quality.ts"] },
    {
      label: "Generated files",
      command: [bun, "tool/entry.ts", "gen", "--check", ...(strict ? ["--strict"] : [])],
    },
  ];
  if (mode === "full") tasks.unshift({ label: "Bun tests", command: [bun, "test"] });
  return tasks;
}
