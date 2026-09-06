import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { runCommandLine } from "../tool/cli";
import { ROOT } from "../tool/core/repo";

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
