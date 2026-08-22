import { basename, resolve } from "node:path";
import { ROOT } from "../support/paths";
import { countResultMarkers, fetchTextWithRetry } from "./http";
import { inspectLivePlugin } from "./plugin_contract";
import { buildProbeUrl } from "./plugin_source";
import type { LiveProbeReport, LiveWorkerArguments } from "./types";

function workerUsage(): string {
  return `Usage: bun test/live_plugin.ts PLUGIN [options]

Options:
  --query QUERY       Search query (default: ubuntu)
  --category CATEGORY qBittorrent category (default: all)
  --allow-empty       Accept a response with no result markers
  --install-only      Validate the plugin contract without making requests
`;
}

export function parseWorkerArguments(rawArgs: string[]): LiveWorkerArguments | null {
  let plugin: string | null = null;
  const args: LiveWorkerArguments = {
    plugin: "",
    query: "ubuntu",
    category: "all",
    allowEmpty: false,
    installOnly: false,
  };

  for (let index = 0; index < rawArgs.length; index += 1) {
    const argument = rawArgs[index];
    if (!argument) {
      continue;
    }
    if (argument === "--help" || argument === "-h") {
      console.log(workerUsage());
      return null;
    }
    if (argument === "--allow-empty") {
      args.allowEmpty = true;
      continue;
    }
    if (argument === "--install-only") {
      args.installOnly = true;
      continue;
    }
    if (!argument.startsWith("-")) {
      if (plugin !== null) {
        throw new Error(`unexpected positional argument: ${argument}`);
      }
      plugin = argument;
      continue;
    }

    const separator = argument.indexOf("=");
    const option = separator < 0 ? argument : argument.slice(0, separator);
    const inlineValue = separator < 0 ? undefined : argument.slice(separator + 1);
    const value = inlineValue ?? rawArgs.at(index + 1);
    if (option !== "--query" && option !== "--category") {
      throw new Error(`unrecognized argument: ${argument}`);
    }
    if (!value || (inlineValue === undefined && value.startsWith("-"))) {
      throw new Error(`${option} requires a value`);
    }
    if (inlineValue === undefined) {
      index += 1;
    }
    if (option === "--query") {
      args.query = value;
    } else {
      args.category = value;
    }
  }

  if (!plugin) {
    throw new Error("a plugin path is required");
  }
  args.plugin = resolve(ROOT, plugin);
  return args;
}

export async function runLiveProbe(args: LiveWorkerArguments): Promise<LiveProbeReport> {
  const contract = await inspectLivePlugin(args.plugin);
  if (contract.errors.length > 0) {
    throw new Error(contract.errors.join("; "));
  }

  if (args.installOnly) {
    return {
      id: contract.id,
      query: args.query,
      category: args.category,
      requests: 0,
      resultMarkers: 0,
      url: null,
      status: null,
      mode: "install-only",
    };
  }

  const url = buildProbeUrl(contract.source, contract.siteUrl, args.query, args.category);
  let requests = 0;
  const response = await fetchTextWithRetry(url, { onRequest: () => (requests += 1) });
  if (response.status >= 400) {
    throw new Error(`remote endpoint returned HTTP ${response.status}`);
  }

  const resultMarkers = countResultMarkers(response.body, response.contentType);
  if (!args.allowEmpty && resultMarkers === 0) {
    throw new Error("live response contained no result markers (use --allow-empty to accept this)");
  }
  return {
    id: contract.id,
    query: args.query,
    category: args.category,
    requests,
    resultMarkers,
    url: response.url,
    status: response.status,
    mode: "probe",
  };
}

function reportLine(report: LiveProbeReport): string {
  if (report.mode === "install-only") {
    return `LIVE PASS ${report.id} [${JSON.stringify(report.query)}]: metadata verified, 0 HTTP requests, TypeScript installability probe`;
  }
  return `LIVE PASS ${report.id} [${JSON.stringify(report.query)}]: ${report.resultMarkers} result markers, ${report.requests} HTTP requests, TypeScript remote probe`;
}

export async function runWorker(rawArgs: string[]): Promise<number> {
  let args: LiveWorkerArguments | null;
  try {
    args = parseWorkerArguments(rawArgs);
  } catch (error) {
    console.error(`LIVE FAIL: ${error instanceof Error ? error.message : String(error)}`);
    console.error(workerUsage());
    return 2;
  }
  if (args === null) {
    return 0;
  }

  try {
    const report = await runLiveProbe(args);
    console.log(reportLine(report));
    return 0;
  } catch (error) {
    const id = basename(args.plugin, ".py");
    console.error(
      `LIVE FAIL ${id} [${JSON.stringify(args.query)}]: ${error instanceof Error ? error.message : String(error)}`,
    );
    return 1;
  }
}
