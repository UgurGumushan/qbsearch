import { runCommand, runPython } from "../core/run";

/** Install pinned repository tools and enable the configured Git hook path. */
export async function setup(args: string[] = []): Promise<number> {
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`Usage: bun run setup [-- --help]

Install pinned Bun/Python checkers and enable the repository pre-commit hook.
`);
    return 0;
  }
  if (args.length > 0) {
    console.error(`unrecognized setup argument: ${args[0]}`);
    return 2;
  }
  const bunExit = await runCommand(
    ["bun", "install", "--frozen-lockfile"],
    "Installing Bun dependencies",
  );
  if (bunExit !== 0) {
    return bunExit;
  }
  const pipExit = await runPython(
    [
      "-m",
      "pip",
      "install",
      "--break-system-packages",
      "--disable-pip-version-check",
      "--requirement",
      "requirements-dev.txt",
    ],
    "Installing Python development tools",
  );
  if (pipExit !== 0) {
    return pipExit;
  }
  return runCommand(["git", "config", "core.hooksPath", ".githooks"], "Enabling repository hooks");
}
