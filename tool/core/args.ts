/**
 * Normalize shared command arguments and generation modes.
 * @file
 */
/** Remove the npm/Bun argument separator before forwarding worker arguments. */
export function stripArgumentSeparator(args: string[]): string[] {
  return args[0] === "--" ? args.slice(1) : args;
}

/** Choose audit or write mode and optional strict metadata validation. */
export interface GenerationOptions {
  mode: "check" | "write";
  strict?: boolean;
}
