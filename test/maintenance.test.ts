import { expect, spyOn, test } from "bun:test";
import { chmod, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { delimiter, resolve } from "node:path";
import { runCommandLine } from "../tool/cli";
import { renderCliDocs } from "../tool/cli-docs";
import { runCheckCommand } from "../tool/commands/check";
import { CHECK_TASKS } from "../tool/checks/tasks";
import { ROOT } from "../tool/core/repo";

test("setup help and invalid arguments never launch installers or Git", async () => {
  const spawn = spyOn(Bun, "spawn").mockImplementation(() => {
    throw new Error("setup must not spawn a process for help or invalid arguments");
  });
  try {
    expect(await runCommandLine(["setup", "--help"])).toBe(0);
    expect(await runCommandLine(["setup", "-h"])).toBe(0);
    expect(await runCommandLine(["setup", "--unknown"])).toBe(2);
    expect(spawn).not.toHaveBeenCalled();
  } finally {
    spawn.mockRestore();
  }
});

test("CLI generation audits by default and writes only when requested", async () => {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-cli-audit-"));
  const fixture = resolve(directory, "CLI.md");
  await writeFile(fixture, "stale documentation\n");
  const originalFile = Bun.file;
  const originalWrite = Bun.write;
  const file = spyOn(Bun, "file").mockImplementation(() => originalFile(fixture));
  const write = spyOn(Bun, "write").mockImplementation((_target, data) => {
    if (typeof data !== "string") throw new Error("CLI documentation must be text");
    return originalWrite(fixture, data);
  });
  try {
    expect(await runCommandLine(["gen", "--only", "cli"])).toBe(1);
    expect(await runCommandLine(["gen", "--only", "cli", "--check"])).toBe(1);
    expect(write).not.toHaveBeenCalled();
    expect(await readFile(fixture, "utf8")).toBe("stale documentation\n");
    expect(await runCommandLine(["gen", "--only", "cli", "--write"])).toBe(0);
    expect(write).toHaveBeenCalledTimes(1);
    expect(await readFile(fixture, "utf8")).toBe(renderCliDocs());
    expect(await runCommandLine(["gen", "--only", "cli"])).toBe(0);
    expect(write).toHaveBeenCalledTimes(1);
  } finally {
    file.mockRestore();
    write.mockRestore();
    await rm(directory, { recursive: true, force: true });
  }
});

const testPosix = process.platform === "win32" ? test.skip : test;

testPosix("both static gates execute every Python checker and propagate failures", async () => {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-checkers-"));
  const log = resolve(directory, "calls.log");
  try {
    for (const name of ["ruff", "basedpyright"]) {
      const path = resolve(directory, name);
      await writeFile(path, '#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$QBSEARCH_CHECK_LOG"\nexit 7\n');
      await chmod(path, 0o755);
    }
    for (const scope of ["static", "staticStrict"] as const) {
      const task = CHECK_TASKS[scope].find((entry) => entry.label === "Python checks");
      if (!task) throw new Error(`${scope} is missing Python checks`);
      await writeFile(log, "");
      const child = Bun.spawn(task.command, {
        cwd: ROOT,
        env: {
          ...process.env,
          PATH: `${directory}${delimiter}${process.env.PATH ?? ""}`,
          QBSEARCH_CHECK_LOG: log,
        },
        stdout: "pipe",
        stderr: "pipe",
      });
      const [code] = await Promise.all([
        child.exited,
        new Response(child.stdout).text(),
        new Response(child.stderr).text(),
      ]);
      expect(code).toBe(7);
      const calls = await readFile(log, "utf8");
      expect(calls).toContain("ruff check .");
      expect(calls).toContain("ruff format --check .");
      expect(calls).toContain("basedpyright");
      expect(calls.trim().split("\n")).toHaveLength(3);
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("fast and full gates preserve worker failures in both strict modes", async () => {
  const originalSpawn = Bun.spawn;
  const spawn = spyOn(Bun, "spawn").mockImplementation((command) => {
    const fail =
      Array.isArray(command) && (command.includes("python") || command.includes("--fast"));
    return originalSpawn([process.execPath, "-e", `process.exit(${fail ? 7 : 0})`], {
      stdout: "ignore",
      stderr: "ignore",
    });
  });
  try {
    for (const args of [[], ["--strict"], ["--fast"], ["--fast", "--strict"]]) {
      expect(await runCheckCommand(args)).toBe(7);
    }
  } finally {
    spawn.mockRestore();
  }
});
