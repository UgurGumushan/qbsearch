import { loadLiveCatalog, type LiveCatalogEntry } from "./live/catalog";
import { parseLiveArguments, type LiveArguments } from "./live/cli";
import {
  logicalCpuCount,
  mapConcurrent,
  pluginPath,
  printFailureDetails,
  runLiveSafety,
  runPlugin,
  type LiveTestResult,
} from "./live/runner";

function selectedPlugins(args: LiveArguments, catalog: LiveCatalogEntry[]): LiveCatalogEntry[] {
  const filtered = catalog.filter(
    (entry) => args.contentCategory === "all" || entry.category === args.contentCategory,
  );
  const entries = new Map(
    filtered
      .filter((entry) => args.pluginIds !== null || entry.status === "active")
      .map((entry) => [entry.id, entry]),
  );
  if (args.pluginIds) {
    const requested = new Set(args.pluginIds);
    const unknown = [...requested]
      .filter((pluginId) => !filtered.some((entry) => entry.id === pluginId))
      .sort();
    if (unknown.length > 0) {
      throw new Error(`unknown or filtered plugin id(s): ${unknown.join(", ")}`);
    }
  }

  const selected = [...entries.values()]
    .filter((entry) => !args.pluginIds || args.pluginIds.includes(entry.id))
    .sort((left, right) => `${left.id}.py`.localeCompare(`${right.id}.py`));
  if (selected.length === 0) {
    throw new Error("no catalog plugins selected");
  }
  return selected;
}

function countSkippedPlugins(args: LiveArguments, catalog: LiveCatalogEntry[]): number {
  if (args.pluginIds) {
    return 0;
  }
  return catalog.filter(
    (entry) =>
      (args.contentCategory === "all" || entry.category === args.contentCategory) &&
      entry.status !== "active",
  ).length;
}

function printRunSummary(args: LiveArguments, count: number, workers: number): void {
  const live = !args.installOnly;
  const mode = live ? "live searches" : "installability checks";
  console.log(`Testing ${count} plugins with ${workers} parallel workers (${mode}).`);
  console.log(`Per-plugin timeout: ${args.timeout}`);
  if (!live) {
    return;
  }
  const queryMode = args.query ? `override: ${JSON.stringify(args.query)}` : "per-plugin defaults";
  console.log(
    `Live queries: ${queryMode} | content category: ${JSON.stringify(args.contentCategory)} | ` +
      `qBittorrent category: ${JSON.stringify(args.category)}`,
  );
  console.log(`Live result policy: ${args.requireResults ? "required" : "empty results allowed"}`);
}

function printPluginResult(result: LiveTestResult): void {
  const status = result.passed ? "PASS" : "FAIL";
  const detail = result.detail ? ` — ${result.detail}` : "";
  console.log(`[${status}] ${result.name} (${result.elapsed.toFixed(2)}s)${detail}`);
}

export async function runLive(rawArgs: string[]): Promise<number> {
  let args: LiveArguments | null;
  try {
    args = parseLiveArguments(rawArgs);
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }
  if (args === null) {
    return 0;
  }
  if (args.timeout <= 0) {
    console.error("ERROR: --timeout must be greater than zero.");
    return 2;
  }

  let catalog: LiveCatalogEntry[];
  try {
    catalog = await loadLiveCatalog();
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }

  let selected: LiveCatalogEntry[];
  try {
    selected = selectedPlugins(args, catalog);
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }

  const workers = logicalCpuCount();
  const skipped = countSkippedPlugins(args, catalog);
  printRunSummary(args, selected.length, workers);
  if (skipped > 0) {
    console.log(
      `Skipping ${skipped} non-active catalog plugin(s); pass --plugin ID to probe one explicitly.`,
    );
  }

  const live = !args.installOnly;
  const allowEmpty = args.allowEmpty || !args.requireResults;
  const results = await mapConcurrent(selected, workers, async (entry) => {
    const result = await runPlugin(
      pluginPath(entry.id),
      args.timeout,
      live,
      args.query ?? entry.defaultQuery,
      args.category,
      allowEmpty,
    );
    printPluginResult(result);
    return result;
  });

  results.sort((left, right) => left.name.localeCompare(right.name));
  const failedPlugins = results.filter((result) => !result.passed);
  console.log(
    `\nPlugin result: ${selected.length - failedPlugins.length} passed, ${failedPlugins.length} failed.`,
  );
  for (const result of failedPlugins) {
    printFailureDetails(result);
  }

  let safetyResult: LiveTestResult | null = null;
  if (args.skipSafety) {
    console.log("Safety helper suite: skipped.");
  } else {
    console.log("\nRunning safety helper suite...");
    safetyResult = await runLiveSafety(args.timeout);
    printPluginResult(safetyResult);
    printFailureDetails(safetyResult);
  }

  if (failedPlugins.length > 0 || (safetyResult !== null && !safetyResult.passed)) {
    console.log("\nOVERALL: FAIL");
    return 1;
  }
  console.log("\nOVERALL: PASS");
  return 0;
}

if (import.meta.main) {
  process.exitCode = await runLive(Bun.argv.slice(2));
}
