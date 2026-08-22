/** Apply the short release-version form used by CI and package scripts. */
export function normalizeReleaseArguments(args: string[]): string[] {
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
