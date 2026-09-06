import type { CheckScope, CheckTask } from "./types";

const BUN = process.execPath;

export const CHECK_TASKS: Record<CheckScope, CheckTask[]> = {
  check: [
    { label: "Bun tests", command: [BUN, "test"] },
    { label: "Static checks", command: [BUN, "tool/entry.ts", "check", "--", "--fast"] },
  ],
  static: [
    { label: "TypeScript", command: [BUN, "run", "typecheck"] },
    { label: "ESLint", command: [BUN, "run", "lint"] },
    { label: "Prettier", command: [BUN, "run", "format:check"] },
    { label: "Python checks", command: [BUN, "tool/checks/command.ts", "python"] },
    { label: "Generated files", command: [BUN, "tool/entry.ts", "gen", "--", "--check"] },
  ],
  python: [
    { label: "Ruff lint", command: ["ruff", "check", "."] },
    { label: "Ruff format", command: ["ruff", "format", "--check", "."] },
    { label: "BasedPyright", command: ["basedpyright"] },
  ],
};
