/** Remove the npm/Bun argument separator before forwarding worker arguments. */
export function stripArgumentSeparator(args: string[]): string[] {
  return args[0] === "--" ? args.slice(1) : args;
}
