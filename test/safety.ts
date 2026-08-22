import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { SAFETY_PREAMBLE } from "../generate/harden/safety_preamble";
import { auditPlugins } from "./safety/plugin_audit";
import { runSafetyPythonHarness } from "./safety/python_harness";

async function waitForRequests(
  counts: Map<string, number>,
  path: string,
  expected: number,
): Promise<void> {
  const deadline = performance.now() + 500;
  while ((counts.get(path) ?? 0) < expected && performance.now() < deadline) {
    await Bun.sleep(10);
  }
}

export async function runSafetySuite(): Promise<void> {
  await auditPlugins();

  const serverCounts = new Map<string, number>();
  const server = Bun.serve({
    port: 0,
    fetch: async (request) => {
      const path = new URL(request.url).pathname;
      const count = (serverCounts.get(path) ?? 0) + 1;
      serverCounts.set(path, count);
      if (path === "/slow") {
        await Bun.sleep(200);
        return new Response("late");
      }
      if (path === "/retry" && count < 3) {
        return new Response("busy", { status: 503 });
      }
      if (path === "/permanent") {
        return new Response("missing", { status: 404 });
      }
      return new Response("ok");
    },
  });

  const temporaryDirectory = await mkdtemp(resolve(tmpdir(), "qbsearch-safety-"));
  const helperPath = resolve(temporaryDirectory, "generated_helpers.py");
  try {
    await writeFile(helperPath, "from __future__ import annotations\n\n" + SAFETY_PREAMBLE, "utf8");
    await runSafetyPythonHarness(helperPath, `http://127.0.0.1:${server.port}`);
    await waitForRequests(serverCounts, "/slow", 3);
    if (serverCounts.get("/ok") !== 1) {
      throw new Error(`expected one /ok request, saw ${serverCounts.get("/ok") ?? 0}`);
    }
    if (serverCounts.get("/slow") !== 3) {
      throw new Error(`expected three /slow requests, saw ${serverCounts.get("/slow") ?? 0}`);
    }
    if (serverCounts.get("/retry") !== 3) {
      throw new Error(`expected three /retry requests, saw ${serverCounts.get("/retry") ?? 0}`);
    }
    if (serverCounts.get("/permanent") !== 1) {
      throw new Error(
        `expected one /permanent request, saw ${serverCounts.get("/permanent") ?? 0}`,
      );
    }
  } finally {
    await server.stop(true);
    await rm(temporaryDirectory, { recursive: true, force: true });
  }
}
