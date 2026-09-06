import { resolve } from "node:path";
import { checkCatalog } from "../checks/catalog";
import { generatePluginCatalog } from "../catalog/command";
import { hardenPlugins } from "../harden/command";
import { makeIcons } from "../icons/command";
import { CLI_DOCS_PATH, ROOT } from "../core/repo";
import { renderCliDocs } from "../cli-docs";
import { checkPluginSources, writePluginSources } from "../generators/plugin-sources";

/** gen --write regenerates; --check audits without editing. */
export async function runGenCommand(rawArgs: string[]): Promise<number> {
  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    console.log(`Usage: bun run gen [-- --check|--write] [--only catalog|harden|icons|cli|sources]

Modes:
  --check  Audit generated files without editing (default in check --fast)
  --write  Regenerate catalog docs, plugin preambles, icons, CLI docs

Examples:
  bun run gen -- --check
  bun run gen -- --write --only catalog
`);
    return 0;
  }
  const onlyArg = rawArgs[rawArgs.indexOf("--only") + 1];
  const only = rawArgs.includes("--only") ? onlyArg : null;
  if (
    rawArgs.includes("--only") &&
    !["catalog", "harden", "icons", "cli", "sources"].includes(only ?? "")
  ) {
    console.error(`unrecognized --only target: ${only ?? "(missing)"}`);
    return 2;
  }
  const write = rawArgs.includes("--write");
  const mode = write ? "--write" : "--check";

  // CLI docs are cheap and always consistent with the router table.
  if (only === "cli") {
    if (!write && rawArgs.includes("--check")) {
      const expected = renderCliDocs();
      const current = (await Bun.file(CLI_DOCS_PATH).exists())
        ? await Bun.file(CLI_DOCS_PATH).text()
        : null;
      if (current !== expected) {
        console.error("ERROR: documentation/CLI.md is out of date; run gen -- --write --only cli");
        return 1;
      }
      return 0;
    }
    await Bun.write(CLI_DOCS_PATH, renderCliDocs());
    console.log("Wrote " + resolve(ROOT, "documentation/CLI.md").replace(ROOT + "/", ""));
    return 0;
  }

  let exit = 0;
  const runCatalog = only === null || only === "catalog";
  const runHarden = only === null || only === "harden";
  const runIcons = only === "icons";
  const runSources = only === null || only === "sources";

  if (runCatalog) {
    if (write) {
      exit = (await generatePluginCatalog(["--docs"])) !== 0 ? 1 : exit;
    } else {
      exit = (await generatePluginCatalog(["--check"])) !== 0 ? 1 : exit;
    }
    if (exit !== 0) {
      return exit;
    }
  }
  if (runHarden) {
    const hardenExit = await hardenPlugins([mode]);
    if (hardenExit !== 0) {
      return hardenExit;
    }
  }
  if (runIcons) {
    if (!write) {
      console.error("icons only supports --write (favicon refresh is not a check)");
      return 2;
    }
    return makeIcons([]);
  }
  if (runSources) {
    if (write) {
      await writePluginSources();
      console.log("Wrote test/plugin_sources.ts");
    } else {
      const drift = await checkPluginSources();
      if (drift !== null) {
        console.error("ERROR: " + drift);
        return 1;
      }
    }
  }
  const runCli = only === null || only === "cli";
  if (runCli && only !== "cli") {
    if (write) {
      await Bun.write(CLI_DOCS_PATH, renderCliDocs());
      console.log("Wrote documentation/CLI.md");
    } else {
      const expected = renderCliDocs();
      const current = (await Bun.file(CLI_DOCS_PATH).exists())
        ? await Bun.file(CLI_DOCS_PATH).text()
        : null;
      if (current !== expected) {
        console.error("ERROR: documentation/CLI.md is out of date; run gen -- --write");
        return 1;
      }
    }
  }
  if (write && only === null) {
    // CLI.md already written above.
  } else if (!write && only === null) {
    exit = (await checkCatalog()) !== 0 ? 1 : exit;
  }
  return exit;
}
