#!/usr/bin/env bun
/**
 * Expose the single-plugin probe worker as a process entrypoint.
 * @file
 */

/**
 * qBittorrent live worker entrypoint. Implementation is split into source,
 * contract, HTTP, and worker modules so this file remains a stable CLI and
 * import surface for the coordinator and deterministic safety suite.
 */

export { inspectLivePlugin } from "./live/plugin_contract";
export { countResultMarkers, fetchTextWithRetry } from "./live/http";
export { buildProbeUrl } from "./live/plugin_source";
export { versionFromSource } from "../tool/core/python-parse";
export { parseWorkerArguments, runLiveProbe, runWorker } from "./live/worker";
export type {
  LivePluginContract,
  LiveProbeReport,
  LiveResponse,
  LiveWorkerArguments,
} from "./live/types";

import { runWorker } from "./live/worker";

if (import.meta.main) {
  process.exitCode = await runWorker(Bun.argv.slice(2));
}
