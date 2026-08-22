import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { runLiveSafetySuite } from "./live_safety";

const ROOT = resolve(import.meta.dir, "..");

test("TypeScript live worker validates contracts and HTTP helpers", async () => {
  await runLiveSafetySuite();
});

test("live test entrypoints do not invoke the Python runtime", async () => {
  const sources = await Promise.all([
    readFile(resolve(ROOT, "test", "live.ts"), "utf8"),
    readFile(resolve(ROOT, "test", "live_plugin.ts"), "utf8"),
    readFile(resolve(ROOT, "test", "live_safety.ts"), "utf8"),
    readFile(resolve(ROOT, "test", "live_watch.ts"), "utf8"),
  ]);
  const source = sources.join("\n");
  expect(source).not.toContain("live_plugin.py");
  expect(source).not.toContain("pythonCommand");
  expect(source).not.toContain("runPython");
});

test("live watch entrypoint tracks catalog and standalone plugin sources", async () => {
  const source = await readFile(resolve(ROOT, "test", "live_watch.ts"), "utf8");
  expect(source).toContain('import "../catalog/plugins.json" with { type: "text" };');
  expect(source).toContain('import "./plugin_sources";');
});
