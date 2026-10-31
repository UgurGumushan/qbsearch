/**
 * Coordinate generated-file writes and drift audits.
 * @file
 */
import { generatePluginCatalog } from "../catalog/command";
import { hardenPlugins } from "../harden/command";
import { checkMaintenanceLog } from "../checks/catalog";
import { CLI_DOCS_PATH } from "../core/repo";
import type { GenerationOptions } from "../core/args";
import { renderCliDocs } from "../cli-docs";
import { checkPluginSources, writePluginSources } from "../generators/plugin-sources";
import { checkProbeFixtures, writeProbeFixtures } from "../../test/live/probe_fixtures";

/** Write CLI documentation or report drift against the router table. */
async function generateCli({ mode }: GenerationOptions): Promise<number> {
  const expected = renderCliDocs();
  if (mode === "write") {
    await Bun.write(CLI_DOCS_PATH, expected);
    console.log("Wrote documentation/CLI.md");
    return 0;
  }
  const current = (await Bun.file(CLI_DOCS_PATH).exists())
    ? await Bun.file(CLI_DOCS_PATH).text()
    : null;
  return reportDrift(current === expected ? [] : ["documentation/CLI.md is out of date"], "cli");
}

/** Print generated-file discrepancies and return a failing status when present. */
function reportDrift(errors: string[], target: string): number {
  if (!errors.length) return 0;
  for (const error of errors) console.error("ERROR: " + error);
  console.error(`Run bun run gen -- --write --only ${target}`);
  return 1;
}

const TARGETS: Record<string, (options: GenerationOptions) => Promise<number>> = {
  catalog: generatePluginCatalog,
  harden: hardenPlugins,
  /** Write or audit the generated plugin watch manifest. */
  sources: async ({ mode }) => {
    if (mode === "write") {
      await writePluginSources();
      console.log("Wrote test/plugin_sources.ts");
      return 0;
    }
    const drift = await checkPluginSources();
    return reportDrift(drift === null ? [] : [drift], "sources");
  },
  /** Write or audit deterministic search-endpoint fixtures. */
  probes: async ({ mode }) => {
    if (mode === "write") {
      await writeProbeFixtures(null);
      return 0;
    }
    return reportDrift(await checkProbeFixtures(), "probes");
  },
  cli: generateCli,
};

/** Parse generation mode and target, rejecting conflicting flags. */
function parseArguments(args: string[]): GenerationOptions & { only: string | null } {
  let mode: GenerationOptions["mode"] = "check";
  let explicitMode = false;
  let strict = false;
  let only: string | null = null;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--check" || arg === "--write") {
      if (explicitMode) throw new Error("choose only one of --check and --write");
      explicitMode = true;
      mode = arg === "--write" ? "write" : "check";
    } else if (arg === "--strict") {
      strict = true;
    } else if (arg === "--only") {
      if (only !== null) throw new Error("--only may be specified once");
      const target = args.at(++index);
      if (target === "icons")
        throw new Error("Icon fetching was retired; add matching .ico files to icons/ directly.");
      if (!target || !Object.hasOwn(TARGETS, target))
        throw new Error(`unrecognized --only target: ${target ?? "(missing)"}`);
      only = target;
    } else {
      throw new Error(`unrecognized gen argument: ${arg}`);
    }
  }
  return { mode, strict, only };
}

/** Audit by default; all targets use the same path for focused and complete runs. */
export async function runGenCommand(args: string[]): Promise<number> {
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`Usage: bun run gen [-- --check|--write] [--only ${Object.keys(TARGETS).join("|")}] [--strict]

  --check  Audit generated files without editing (default)
  --write  Regenerate selected files
  --strict Treat catalog metadata warnings as failures
`);
    return 0;
  }
  let options: ReturnType<typeof parseArguments>;
  try {
    options = parseArguments(args);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  }
  for (const [name, generate] of Object.entries(TARGETS)) {
    if (options.only !== null && options.only !== name) continue;
    const exit = await generate(options);
    if (exit !== 0) return exit;
  }
  return options.only === null && options.mode === "check" ? checkMaintenanceLog() : 0;
}
