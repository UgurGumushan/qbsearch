import { homedir } from "node:os";
import type { ParsedArguments } from "./types";
import { DEFAULT_OUTPUT } from "./constants";

export function usage(): string {
  return `Usage: bun run release -- [version] [--version VERSION] [--output PATH]

Build a self-contained qBittorrent plugin release ZIP.
`;
}

export function parseArguments(args: string[]): ParsedArguments {
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

export function expandHome(path: string): string {
  return path.replace(/^~(?=$|[\\/])/, homedir());
}
