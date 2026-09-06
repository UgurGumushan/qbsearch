import { resolve } from "node:path";
import { buildRelease } from "./release/command";
import { normalizeReleaseArguments } from "./release/command_arguments";
import { checkCatalog } from "./checks/catalog";
import { ROOT } from "./core/repo";
import { runCommand } from "./core/run";
import { runCheckCommand } from "./commands/check";
import { runGenCommand } from "./commands/gen";
import { runPluginCommand } from "./commands/plugin";
import { setup } from "./commands/setup";
import { stripArgumentSeparator } from "./core/args";
import { importUpstreamPlugins } from "./upstream";

export interface CommandSpec {
  name: string;
  description: string;
  examples: string[];
}

/** Single source of truth for repository commands. */
export const COMMANDS: CommandSpec[] = [
  {
    name: "setup",
    description: "Install pinned Bun/Python checkers and enable the pre-commit hook.",
    examples: ["bun run setup"],
  },
  {
    name: "check",
    description:
      "Run deterministic checks. --fast is the pre-commit hook subset; --full (default) adds bun test.",
    examples: ["bun run check", "bun run check -- --fast", "bun run check -- --full"],
  },
  {
    name: "gen",
    description: "Regenerate or audit generated files (catalog docs, preambles, icons, CLI docs).",
    examples: ["bun run gen -- --check", "bun run gen -- --write --only catalog"],
  },
  {
    name: "plugin",
    description: "Validate or scaffold standalone plugins.",
    examples: ["bun run plugin -- --validate", "bun run plugin -- --new myengine --kind json"],
  },
  {
    name: "test",
    description: "Run deterministic bun tests, or live network tests with --live.",
    examples: [
      "bun run test",
      "bun run test -- --watch",
      "bun run test -- --live --plugin yts",
      "bun run test -- --live --plugin yts --require-results",
    ],
  },
  {
    name: "release",
    description: "Build a release ZIP after validating the catalog.",
    examples: ["bun run release -- 0.1.3"],
  },
];

export function printHelp(): void {
  const rows = COMMANDS.map((c) => `  ${c.name.padEnd(10)} ${c.description}`).join("\n");
  console.log(`Usage: bun run <command> [-- arguments]\n\nCommands:\n${rows}\n`);
}

async function runLive(args: string[]): Promise<number> {
  const catalogExit = await checkCatalog();
  if (catalogExit !== 0) {
    return catalogExit;
  }
  const watch = args.includes("--watch");
  const rest = args.filter((a) => a !== "--watch");
  const entry = resolve(ROOT, "test", watch ? "live_watch.ts" : "live.ts");
  const argv = watch
    ? [process.execPath, "--watch", entry, ...rest]
    : [process.execPath, entry, ...rest];
  return runCommand(argv, "Live plugin tests");
}

async function runDeterministicTest(args: string[]): Promise<number> {
  if (args.includes("--live")) {
    return runLive(args.filter((a) => a !== "--live"));
  }
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`Usage: bun run test [-- --watch|--live ...]

  (no flags)           Run the deterministic Bun test suite
  --watch              Keep Bun tests watching plugins/
  --live [live flags]  Run live network tests (pass-through to test/live.ts)
`);
    return 0;
  }
  if (args.includes("--watch")) {
    return runCommand([process.execPath, "test", "--watch"], "Bun tests (watch)");
  }
  return runCommand([process.execPath, "test"], "Bun tests");
}

/** Dispatch one repository maintenance command. */
export async function runCommandLine(rawArgs: string[]): Promise<number> {
  const command = rawArgs[0] ?? "help";
  const args = stripArgumentSeparator(rawArgs.slice(1));
  switch (command) {
    case "setup":
      return setup();
    case "check":
      return runCheckCommand(args);
    case "gen":
      return runGenCommand(args);
    case "plugin":
      return runPluginCommand(args);
    case "test":
      return runDeterministicTest(args);
    case "release": {
      const catalogExit = await checkCatalog();
      if (catalogExit !== 0) {
        return catalogExit;
      }
      return buildRelease(normalizeReleaseArguments(args));
    }
    case "help":
    case "--help":
    case "-h":
      printHelp();
      return 0;
    // Legacy aliases — kept working, documented in CLI.md as deprecated.
    case "static":
    case "static-check":
      console.warn("Deprecated: use 'bun run check -- --fast' instead of static-check.");
      return runCheckCommand(
        args.includes("--help") || args.includes("-h") ? ["--help"] : ["--fast"],
      );
    case "python":
    case "python:check":
      console.warn("Deprecated: use 'bun run check -- --fast' instead of python:check.");
      return runCommand([process.execPath, "run", "python:check"], "Python checks");
    case "catalog":
      console.warn("Deprecated: use 'bun run gen -- --write --only catalog' instead of catalog.");
      if (args.includes("--help") || args.includes("-h")) {
        return runGenCommand(["--help"]);
      }
      return runGenCommand(args.length > 0 ? args : ["--write", "--only", "catalog"]);
    case "harden":
      console.warn("Deprecated: use 'bun run gen -- [--check|--write] --only harden' instead.");
      if (args.includes("--help") || args.includes("-h")) {
        return runGenCommand(["--help"]);
      }
      return runGenCommand(
        args.length > 0 ? [...args, "--only", "harden"] : ["--check", "--only", "harden"],
      );
    case "icons":
      console.warn("Deprecated: use 'bun run gen -- --write --only icons' instead of icons.");
      return runGenCommand(["--write", "--only", "icons"]);
    case "upstream":
      console.warn("Deprecated alias: upstream is now under gen (kept for compatibility).");
      return importUpstreamPlugins(args);
    case "test-live":
    case "test:live":
      console.warn("Deprecated: use 'bun run test -- --live ...' instead of test:live.");
      return runLive(args);
    case "test-live-watch":
    case "test:live:watch":
      console.warn("Deprecated: use 'bun run test -- --live --watch ...' instead.");
      return runLive([...args, "--watch"]);
    default:
      console.error(`Unknown command '${command}'. Run 'bun run help' for usage.`);
      return 2;
  }
}
