import { expect, spyOn, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { tmpdir } from "node:os";
import { runCommandLine } from "../tool/cli";
import { ROOT } from "../tool/core/repo";

async function scaffoldLocation() {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-command-scaffold-"));
  const path = resolve(directory, "engine.py");
  const originalFile = Bun.file;
  const originalWrite = Bun.write;
  const file = spyOn(Bun, "file").mockImplementation(() => originalFile(path));
  const write = spyOn(Bun, "write").mockImplementation((_target, data) => {
    if (typeof data !== "string") throw new Error("scaffold source must be text");
    return originalWrite(path, data);
  });
  return {
    path,
    cleanup: async () => {
      file.mockRestore();
      write.mockRestore();
      await rm(directory, { recursive: true, force: true });
    },
  };
}

test("canonical command routing exposes the six commands", async () => {
  for (const command of ["setup", "check", "gen", "plugin", "test", "release", "help"]) {
    expect(await runCommandLine([command, "--help"])).toBe(0);
  }
});

test("canonical command routing rejects unknown commands", async () => {
  expect(await runCommandLine(["not-a-command"])).toBe(2);
});

test("retired aliases are rejected as unknown commands", async () => {
  for (const retired of ["static-check", "catalog", "harden", "test:live", "upstream"]) {
    expect(await runCommandLine([retired])).toBe(2);
  }
});

test("maintenance package scripts use the shared command router", async () => {
  const packageJson = JSON.parse(await readFile(resolve(ROOT, "package.json"), "utf8")) as {
    scripts: Record<string, string>;
  };

  expect(packageJson.scripts.setup).toBe("bun tool/entry.ts setup");
  expect(packageJson.scripts.check).toBe("bun tool/entry.ts check");
  expect(packageJson.scripts.gen).toBe("bun tool/entry.ts gen");
  expect(packageJson.scripts.plugin).toBe("bun tool/entry.ts plugin");
  expect(packageJson.scripts.test).toBe("bun tool/entry.ts test");
  expect(packageJson.scripts.release).toBe("bun tool/entry.ts release");
});

test("plugin --new json scaffold writes a valid starter and respects --site", async () => {
  const pluginId = `tmp_scaffold_${randomUUID().replace(/-/g, "")}`;
  const { path, cleanup } = await scaffoldLocation();

  try {
    expect(
      await runCommandLine([
        "plugin",
        "--new",
        pluginId,
        "--kind",
        "json",
        "--site",
        "https://example.test",
      ]),
    ).toBe(0);
    const source = await readFile(path, "utf8");
    expect(source).toContain(`class ${pluginId}:`);
    expect(source).toContain('url = "https://example.test"');
    expect(source).toContain("# QBSEARCH-PREAMBLE-ANCHOR");
    expect(source).toContain("Replace the placeholder request and parsing logic");
    expect(await runCommandLine(["plugin", "--new", pluginId, "--kind", "json"])).toBe(1);
  } finally {
    await cleanup();
  }
});

test("plugin --new html scaffold is generated and writes parse placeholders", async () => {
  const pluginId = `tmp_scaffold_html_${randomUUID().replace(/-/g, "")}`;
  const { path, cleanup } = await scaffoldLocation();

  try {
    expect(
      await runCommandLine([
        "plugin",
        "--new",
        pluginId,
        "--kind",
        "html",
        "--site",
        "https://example.test",
      ]),
    ).toBe(0);
    const source = await readFile(path, "utf8");
    expect(source).toContain(`class ${pluginId}:`);
    expect(source).toContain("Replace the placeholder request and parsing logic");
  } finally {
    await cleanup();
  }
});

test("plugin --new rejects unsupported template kind", async () => {
  const pluginId = `tmp_scaffold_unsupported_${randomUUID().replace(/-/g, "")}`;
  const path = resolve(ROOT, "plugins", `${pluginId}.py`);

  expect(await runCommandLine(["plugin", "--new", pluginId, "--kind", "xml"])).toBe(2);
  await rm(path, { force: true });
});
