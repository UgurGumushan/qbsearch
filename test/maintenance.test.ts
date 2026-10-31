/**
 * Verify maintenance commands, generated-file modes, and safety injection.
 * @file
 */
import { expect, spyOn, test } from "bun:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { runCommandLine } from "../tool/cli";
import { renderCliDocs } from "../tool/cli-docs";
import { runCheckCommand } from "../tool/commands/check";
import { checkTasks } from "../tool/checks/tasks";

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

test("fast and full gates run every checker and preserve failures in both strict modes", async () => {
  const originalSpawn = Bun.spawn;
  const calls: string[][] = [];
  const spawn = spyOn(Bun, "spawn").mockImplementation((command) => {
    if (!Array.isArray(command)) throw new Error("expected command arguments");
    const argv = command.map(String);
    calls.push(argv);
    return originalSpawn(
      [process.execPath, "-e", `process.exit(${argv[0] === "basedpyright" ? 7 : 0})`],
      {
        stdout: "ignore",
        stderr: "ignore",
      },
    );
  });
  try {
    for (const mode of ["fast", "full"] as const) {
      for (const strict of [false, true]) {
        calls.length = 0;
        expect(await runCheckCommand([`--${mode}`, ...(strict ? ["--strict"] : [])])).toBe(7);
        expect(calls.filter((argv) => argv[0] === "ruff")).toEqual([
          ["ruff", "check", "."],
          ["ruff", "format", "--check", "."],
        ]);
        expect(calls.filter((argv) => argv[0] === "basedpyright")).toEqual([["basedpyright"]]);
        expect(calls.filter((argv) => argv[1] === "test")).toHaveLength(mode === "full" ? 1 : 0);
        expect(calls.filter((argv) => argv.includes("gen"))).toEqual([
          [process.execPath, "tool/entry.ts", "gen", "--check", ...(strict ? ["--strict"] : [])],
        ]);
        expect(calls).toHaveLength(checkTasks({ mode, strict }).length);
      }
    }
  } finally {
    spawn.mockRestore();
  }
});

test("retired and invalid command options fail before writing or launching work", async () => {
  const spawn = spyOn(Bun, "spawn").mockImplementation(() => {
    throw new Error("unexpected subprocess");
  });
  const write = spyOn(Bun, "write").mockImplementation(() => {
    throw new Error("unexpected write");
  });
  try {
    for (const args of [
      ["gen", "--write", "--only", "icons"],
      ["gen", "--write", "--check"],
      ["gen", "--only"],
      ["gen", "--only", "cli", "--only", "probes"],
      ["gen", "--unknown"],
      ["release", "--output"],
      ["test", "--unknown"],
      ["test", "--live", "--plugin"],
      ...["--benchmark", "--baseline=HEAD", "--samples", "--warmups", "--matrix"].map((flag) => [
        "test",
        flag,
      ]),
      ["test", "--live", "--benchmark"],
    ])
      expect(await runCommandLine(args)).toBe(2);
    expect(spawn).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
  } finally {
    spawn.mockRestore();
    write.mockRestore();
  }
});
