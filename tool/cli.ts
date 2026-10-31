/**
 * Define the supported maintainer commands and dispatch their implementations.
 * @file
 */
import { stripArgumentSeparator } from "./core/args";

/** Command routing metadata shared by execution, help, and generated CLI docs. */
export interface CommandSpec {
  name: string;
  description: string;
  examples: string[];
  run: (args: string[]) => Promise<number>;
}

/** Single source of truth for repository commands. */
export const COMMANDS: CommandSpec[] = [
  {
    name: "setup",
    /** Load and invoke this command only when its route is selected. */
    run: async (args) => (await import("./commands/setup")).setup(args),
    description: "Install pinned Bun/Python checkers and enable the pre-commit hook.",
    examples: ["bun run setup"],
  },
  {
    name: "check",
    /** Load and invoke this command only when its route is selected. */
    run: async (args) => (await import("./commands/check")).runCheckCommand(args),
    description:
      "Run deterministic checks. --fast is the pre-commit hook subset; --full (default) adds bun test. --strict enforces metadata warnings as failures.",
    examples: [
      "bun run check",
      "bun run check -- --fast",
      "bun run check -- --full",
      "bun run check -- --strict",
    ],
  },
  {
    name: "gen",
    /** Load and invoke this command only when its route is selected. */
    run: async (args) => (await import("./commands/gen")).runGenCommand(args),
    description:
      "Regenerate or audit generated files (catalog docs, preambles, watch sources, probes, CLI docs).",
    examples: ["bun run gen -- --check", "bun run gen -- --write --only catalog"],
  },
  {
    name: "plugin",
    /** Load and invoke this command only when its route is selected. */
    run: async (args) => (await import("./commands/plugin")).runPluginCommand(args),
    description: "Validate or scaffold standalone plugins.",
    examples: ["bun run plugin -- --validate", "bun run plugin -- --new myengine --kind json"],
  },
  {
    name: "test",
    /** Load and invoke this command only when its route is selected. */
    run: async (args) => (await import("./commands/test")).runTestCommand(args),
    description: "Run deterministic tests or live network tests (--live).",
    examples: [
      "bun run test",
      "bun run test -- --watch",
      "bun run test -- --live --plugin yts",
      "bun run test -- --live --plugin yts --require-results",
      "bun run test -- --live --record-probes",
    ],
  },
  {
    name: "release",
    /** Load and invoke this command only when its route is selected. */
    run: async (args) => (await import("./commands/release")).runReleaseCommand(args),
    description: "Build a release ZIP after validating the catalog.",
    examples: ["bun run release -- 0.1.3"],
  },
];

/** Render top-level help from the canonical command registry. */
export function printHelp(): void {
  const rows = COMMANDS.map((c) => `  ${c.name.padEnd(10)} ${c.description}`).join("\n");
  console.log(`Usage: bun run <command> [-- arguments]\n\nCommands:\n${rows}\n`);
}

/** Dispatch one repository maintenance command. */
export async function runCommandLine(rawArgs: string[]): Promise<number> {
  const name = rawArgs[0] ?? "help";
  if (["help", "--help", "-h"].includes(name)) {
    printHelp();
    return 0;
  }
  const command = COMMANDS.find((entry) => entry.name === name);
  if (!command) {
    console.error(`Unknown command '${name}'. Run 'bun run help' for usage.`);
    return 2;
  }
  return command.run(stripArgumentSeparator(rawArgs.slice(1)));
}
