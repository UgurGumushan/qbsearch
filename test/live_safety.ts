#!/usr/bin/env bun

import { basename } from "node:path";
import { countResultMarkers, fetchTextWithRetry, inspectLivePlugin } from "./live_plugin";
import { PLUGIN_SOURCES } from "./plugin_sources";
import { discoverCatalogPlugins } from "./support/plugin_inventory";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

export async function runLiveSafetySuite(): Promise<void> {
  const plugins = await discoverCatalogPlugins();
  for (const path of plugins) {
    const id = basename(path, ".py");
    const source = Object.hasOwn(PLUGIN_SOURCES, id)
      ? PLUGIN_SOURCES[id as keyof typeof PLUGIN_SOURCES]
      : undefined;
    assert(source !== undefined, `${id}: missing static Bun source dependency`);
    const contract = await inspectLivePlugin(path, source);
    assert(contract.errors.length === 0, `${contract.id}: ${contract.errors.join("; ")}`);
  }

  const counts = new Map<string, number>();
  const server = Bun.serve({
    port: 0,
    fetch: async (request) => {
      const path = new URL(request.url).pathname;
      counts.set(path, (counts.get(path) ?? 0) + 1);
      if (path === "/slow") {
        await Bun.sleep(200);
        return new Response("late");
      }
      if (path === "/retry" && (counts.get(path) ?? 0) < 3) {
        return new Response("busy", { status: 503 });
      }
      if (path === "/permanent") {
        return new Response("missing", { status: 404 });
      }
      return Response.json({ torrents: [{ link: "magnet:?xt=urn:btih:fixture" }] });
    },
  });

  try {
    await fetchTextWithRetry(`http://127.0.0.1:${server.port}/slow`, {
      timeoutMs: 50,
      maxAttempts: 3,
    }).catch(() => undefined);
    assert(
      counts.get("/slow") === 3,
      `expected three timeout attempts, saw ${counts.get("/slow")}`,
    );

    const retried = await fetchTextWithRetry(`http://127.0.0.1:${server.port}/retry`);
    assert(retried.status === 200, `expected retry endpoint to succeed, saw ${retried.status}`);
    assert(retried.attempts === 3, `expected three retry attempts, saw ${retried.attempts}`);

    const permanent = await fetchTextWithRetry(`http://127.0.0.1:${server.port}/permanent`);
    assert(permanent.status === 404, `expected permanent 404, saw ${permanent.status}`);
    assert(permanent.attempts === 1, `expected one permanent request, saw ${permanent.attempts}`);
    assert(countResultMarkers(retried.body, retried.contentType) === 1, "JSON marker scan failed");
  } finally {
    await server.stop(true);
  }

  console.log("TypeScript live helper tests passed.");
}

if (import.meta.main) {
  try {
    await runLiveSafetySuite();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
