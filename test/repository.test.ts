import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { expect, setDefaultTimeout, test } from "bun:test";
import {
  CATALOG_PATH,
  DOCS_PATH,
  catalogEntries,
  discoverPlugins,
  loadCatalog,
  renderPluginDocs,
} from "../generate/catalog/index";
import { validateCatalog } from "../check/catalog_validation";
import { auditPlugin } from "../check/harden/audit_plugin";
import { runSafetySuite } from "./safety";
import { PLUGIN_SOURCES } from "./plugin_sources";
import { assertPassed, runPython } from "./support/process";

setDefaultTimeout(120_000);

test("Bun tracks every standalone plugin source", async () => {
  const pluginPaths = await discoverPlugins();
  const diskIds = pluginPaths.map((path) => basename(path, ".py"));
  const diskSources: Record<string, string> = {};
  for (const path of pluginPaths) {
    diskSources[basename(path, ".py")] = await readFile(path, "utf8");
  }
  const catalog = await loadCatalog(CATALOG_PATH);
  const catalogIds = catalogEntries(catalog).map((entry) => entry.id);

  expect(Object.keys(PLUGIN_SOURCES).sort()).toEqual(diskIds);
  expect(diskSources).toEqual(PLUGIN_SOURCES);
  expect(Object.keys(PLUGIN_SOURCES).sort()).toEqual(catalogIds.sort());
});

test("catalog and generated plugin documentation are current", async () => {
  const catalog = await loadCatalog(CATALOG_PATH);
  expect(await validateCatalog(catalog)).toEqual([]);
  expect(await readFile(DOCS_PATH, "utf8")).toBe(renderPluginDocs(catalog));
});

test("safety helpers pass their deterministic fake-server suite", async () => {
  await runSafetySuite();
});

test("standalone plugin safety preambles are current", async () => {
  const failures: string[] = [];
  for (const path of await discoverPlugins()) {
    const errors = await auditPlugin(path);
    failures.push(...errors.map((error) => `${basename(path)}: ${error}`));
  }
  expect(failures).toEqual([]);
});

test("plugins compile and remain installable", async () => {
  assertPassed("Python compilation", await runPython(["-m", "compileall", "-q", "plugins"]));
  const result = await runPython(["test/engines.py", "plugins"]);
  assertPassed("plugin installability", result);
  expect(result.output).toContain("INSTALLABLE");
});
