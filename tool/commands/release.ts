/**
 * Parse release options and build a validated distribution archive.
 * @file
 */
import type { ReleaseOptions } from "../release/types";
import { buildRelease } from "../release/command";
import { checkCatalog } from "../checks/catalog";
import { DEFAULT_OUTPUT } from "../release/constants";

/** Describe release version and output-path arguments. */
function usage(): string {
  return `Usage: bun run release -- [version] [--version VERSION] [--output PATH]

Build a self-contained qBittorrent plugin release ZIP.
`;
}

/** Normalize release options and reject unsupported or incomplete arguments. */
export function parseReleaseArguments(args: string[]): ReleaseOptions & { help: boolean } {
  args = normalizeReleaseArguments(args);
  let version = "dev";
  let output = DEFAULT_OUTPUT;
  let positionalVersion = false;

  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--help" || argument === "-h") {
      return { help: true, version, output };
    }
    if (argument === "--version" || argument === "--output") {
      const value = args[index + 1];
      if (!value || value.startsWith("--")) {
        throw new Error(`${argument} requires a value`);
      }
      if (argument === "--version") {
        version = value;
      } else {
        output = value;
      }
      index += 1;
      continue;
    }
    if (argument.startsWith("--version=")) {
      version = argument.slice("--version=".length);
      continue;
    }
    if (argument.startsWith("--output=")) {
      output = argument.slice("--output=".length);
      continue;
    }
    if (argument.startsWith("-")) {
      throw new Error(`unrecognized argument: ${argument}`);
    }
    if (positionalVersion) {
      throw new Error(`unexpected argument: ${argument}`);
    }
    version = argument;
    positionalVersion = true;
  }

  return { help: false, version, output };
}

/** Apply the short release-version form used by CI and package scripts. */
function normalizeReleaseArguments(args: string[]): string[] {
  if (args.length === 1 && !args[0].startsWith("-")) {
    const version = args[0];
    return ["--version", version, "--output", `working/qbsearch-${version}.zip`];
  }
  if (args.length === 0 && process.env.VERSION) {
    const version = process.env.VERSION;
    return ["--version", version, "--output", `working/qbsearch-${version}.zip`];
  }
  return args;
}

/** Parse the public release interface before validating or writing the archive. */
export async function runReleaseCommand(rawArgs: string[]): Promise<number> {
  let options: ReturnType<typeof parseReleaseArguments>;
  try {
    options = parseReleaseArguments(rawArgs);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  }
  if (options.help) {
    console.log(usage());
    return 0;
  }
  const exit = await checkCatalog();
  return exit === 0 ? buildRelease(options) : exit;
}
