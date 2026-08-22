import { resolve } from "node:path";
import { buildRelease } from "../../release/command";
import { generatePluginCatalog } from "../../generate/catalog/command";
import { hardenPlugins } from "../../generate/harden/command";
import { importUpstreamPlugins } from "../../generate/upstream/command";
import { makeIcons } from "../../generate/icons/command";
import { ROOT } from "../repository";
import { runCommand } from "../process";
import { stripArgumentSeparator } from "./arguments";
import { checkCatalog } from "../../check/catalog";
import { printHelp } from "./help";
import { normalizeReleaseArguments } from "../../release/command_arguments";
import { setup } from "./setup";
import { runChecks } from "../../check/command";

/** Dispatch one repository maintenance command. */
export async function runCommandLine(rawArgs: string[]): Promise<number> {
  const command = rawArgs[0] ?? "help";
  const args = stripArgumentSeparator(rawArgs.slice(1));

  switch (command) {
    case "check":
      return runChecks(args.length > 0 ? args : ["check"]);
    case "static":
    case "static-check":
      return runChecks(args.length > 0 ? args : ["static"]);
    case "python":
    case "python:check":
      return runChecks(args.length > 0 ? args : ["python"]);
    case "setup":
      return setup();
    case "catalog":
      return generatePluginCatalog(args);
    case "harden":
      return hardenPlugins(args.length > 0 ? args : ["--check"]);
    case "icons":
      return makeIcons(args);
    case "upstream":
      return importUpstreamPlugins(args);
    case "test-live": {
      const catalogExit = await checkCatalog();
      if (catalogExit !== 0) {
        return catalogExit;
      }
      return runCommand(
        [process.execPath, resolve(ROOT, "test", "live.ts"), ...args],
        "Live plugin tests",
      );
    }
    case "test-live-watch": {
      if (args.includes("--help") || args.includes("-h")) {
        const catalogExit = await checkCatalog();
        if (catalogExit !== 0) {
          return catalogExit;
        }
        return runCommand(
          [process.execPath, resolve(ROOT, "test", "live.ts"), ...args],
          "Live plugin tests",
        );
      }
      return runCommand(
        [process.execPath, "--watch", resolve(ROOT, "test", "live_watch.ts"), ...args],
        "Live plugin tests (watch)",
      );
    }
    case "release": {
      const catalogExit = await checkCatalog();
      if (catalogExit !== 0) {
        return catalogExit;
      }
      return buildRelease(normalizeReleaseArguments(args));
    }
    case "help":
      printHelp();
      return 0;
    default:
      console.error(`Unknown command '${command}'. Run 'bun scripts/commands.ts help' for usage.`);
      return 2;
  }
}
