import { resolve } from "node:path";
import { checkCatalog } from "../checks/catalog";
import { ROOT } from "../core/repo";
import { runCommand } from "../core/run";
import { parseLiveArguments } from "../../test/live/cli";

const RETIRED_OPTIONS = new Set([
  "--benchmark",
  "--baseline",
  "--samples",
  "--warmups",
  "--matrix",
]);

/** Run deterministic tests or the isolated Bun live workers. */
export async function runTestCommand(args: string[]): Promise<number> {
  try {
    const retired = args.find((arg) => RETIRED_OPTIONS.has(arg.split("=", 1)[0]));
    if (retired)
      throw new Error(`${retired} was retired; use bun run test for deterministic regressions.`);
    if (args.includes("--live")) {
      const watch = args.includes("--watch");
      const rest = args.filter((arg) => arg !== "--live" && arg !== "--watch");
      if (parseLiveArguments(rest) === null) return 0;
      const catalogExit = await checkCatalog();
      if (catalogExit !== 0) return catalogExit;
      const entry = resolve(ROOT, "test", watch ? "live_watch.ts" : "live.ts");
      return await runCommand(
        [process.execPath, ...(watch ? ["--watch"] : []), entry, ...rest],
        "Live plugin tests",
      );
    }
    if (args.includes("--help") || args.includes("-h")) {
      console.log(`Usage: bun run test [-- --watch|--live ...]

  (no flags)           Run the deterministic Bun test suite
  --watch              Keep Bun tests watching plugins/
  --live [live flags]  Run live network tests; add --help for live flags
`);
      return 0;
    }
    for (const arg of args) {
      if (arg !== "--watch") throw new Error(`unrecognized test argument: ${arg}`);
    }
    return await runCommand(
      [process.execPath, "test", ...(args.includes("--watch") ? ["--watch"] : [])],
      "Bun tests",
    );
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  }
}
