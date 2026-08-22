import { runCommand, runPython } from "../process";

/** Install pinned repository tools and enable the configured Git hook path. */
export async function setup(): Promise<number> {
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
