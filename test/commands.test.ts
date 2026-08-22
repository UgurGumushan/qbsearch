import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { runCommandLine } from "../scripts/command/cli";
import { ROOT } from "../scripts/repository";

test("canonical command routing exposes check scopes", async () => {
  expect(await runCommandLine(["check", "--help"])).toBe(0);
  expect(await runCommandLine(["static-check", "--help"])).toBe(0);
  expect(await runCommandLine(["python:check", "--help"])).toBe(0);
});

test("canonical command routing rejects unknown commands", async () => {
  expect(await runCommandLine(["not-a-command"])).toBe(2);
});

test("maintenance package scripts use the shared command router", async () => {
  const packageJson = JSON.parse(await readFile(resolve(ROOT, "package.json"), "utf8")) as {
    scripts: Record<string, string>;
  };

  expect(packageJson.scripts.check).toBe("bun scripts/commands.ts check");
  expect(packageJson.scripts.catalog).toBe("bun scripts/commands.ts catalog");
  expect(packageJson.scripts.harden).toBe("bun scripts/commands.ts harden");
  expect(packageJson.scripts.icons).toBe("bun scripts/commands.ts icons");
  expect(packageJson.scripts.release).toBe("bun scripts/commands.ts release");
  expect(packageJson.scripts.upstream).toBe("bun scripts/commands.ts upstream");
});
