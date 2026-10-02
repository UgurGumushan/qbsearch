import { pythonCommand, runCapturedCommand } from "../../tool/core/run";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

export type ParserPlugin =
  | "elitetorrent"
  | "bitsearch"
  | "solidtorrents"
  | "ali213"
  | "pirateiro"
  | "traht"
  | "audiobookbay"
  | "darklibria"
  | "dmhy"
  | "torrentdownloads"
  | "uniondht";

export type FixtureReply =
  | string
  | {
      body?: string;
      bodyBase64?: string;
      status?: number;
      finalUrl?: string;
      headers?: Record<string, string>;
      delayMs?: number;
    };

export interface ParserCase {
  plugin: string;
  query: string;
  category?: string;
  action?: "search" | "detail" | "download";
  detailUrl?: string;
  maxPages?: number;
  maxDetails?: number;
  maxWorkers?: number;
  responses: Record<string, FixtureReply>;
  exchanges?: { url: string; method: "GET" | "POST"; data?: string; response: FixtureReply }[];
  cacheXml?: string;
  cacheFresh?: boolean;
  emptyResponse?: FixtureReply;
  expectEmpty?: boolean;
  sourceSha256?: string;
  verifiedDownloads?: string[];
  responseDelayMs?: number;
  deadlineMs?: number;
  repeatSearches?: number;
}

export interface ReplayMetrics {
  importSeconds: number;
  firstResultSeconds: number | null;
  totalSeconds: number;
  cpuSeconds: number;
  responseBytes: number;
  usableResults: number;
  peakAllocatedBytes: number | null;
  peakRssBytes: number | null;
}

export interface ReplayOptions {
  sourceRoot?: string;
  measure?: boolean;
  trace?: boolean;
  timeoutSeconds?: number;
}

export interface ParserReport {
  code: number;
  records: Record<string, unknown>[];
  requests: string[];
  errors: string[];
  downloadRequests: string[];
  output: string[];
  peakConcurrentRequests?: number;
  requestConcurrency?: number[];
  requestDetails?: {
    url: string;
    method: string;
    data: string;
    headers: Record<string, unknown>;
    status: number | null;
    fixtureBytes: number;
    finalUrl: string;
  }[];
  sourceSha256?: string;
  python?: string;
  metrics?: ReplayMetrics;
  processSeconds?: number;
  resultRequestCounts?: number[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** This subprocess consumes saved responses only; it never fetches a site. */
export async function replayParserCase(
  path: string,
  options: ReplayOptions = {},
): Promise<ParserReport> {
  const flags = [
    ...(options.sourceRoot ? ["--source-root", options.sourceRoot] : []),
    ...(options.measure ? ["--measure"] : []),
    ...(options.trace ? ["--trace"] : []),
  ];
  const result = await runCapturedCommand(
    [...pythonCommand(), "-m", "test.parser_harness", path, ...flags],
    {
      timeoutSeconds: options.timeoutSeconds ?? 10,
    },
  );
  const value = JSON.parse(result.output) as unknown;
  if (
    !isRecord(value) ||
    !Array.isArray(value.records) ||
    !value.records.every(isRecord) ||
    !Array.isArray(value.requests) ||
    !value.requests.every((item: unknown) => typeof item === "string") ||
    !Array.isArray(value.errors) ||
    !value.errors.every((item: unknown) => typeof item === "string") ||
    !Array.isArray(value.downloadRequests) ||
    !value.downloadRequests.every((item: unknown) => typeof item === "string") ||
    !Array.isArray(value.output) ||
    !value.output.every((item: unknown) => typeof item === "string")
  ) {
    throw new Error(`invalid parser report: ${result.output}`);
  }
  const metrics = isRecord(value.metrics) ? value.metrics : undefined;
  const requiredMetrics = [
    "importSeconds",
    "totalSeconds",
    "cpuSeconds",
    "responseBytes",
    "usableResults",
  ];
  if (
    options.measure &&
    (!metrics || requiredMetrics.some((key) => typeof metrics[key] !== "number"))
  ) {
    throw new Error(`missing replay measurements: ${result.output}`);
  }
  const numeric = (key: string): number => Number(metrics?.[key] ?? 0);
  const nullable = (key: string): number | null =>
    typeof metrics?.[key] === "number" ? metrics[key] : null;
  return {
    code: result.code,
    records: value.records,
    requests: value.requests,
    errors: value.errors,
    downloadRequests: value.downloadRequests,
    output: value.output,
    peakConcurrentRequests:
      typeof value.peakConcurrentRequests === "number" ? value.peakConcurrentRequests : 0,
    requestConcurrency: Array.isArray(value.requestConcurrency)
      ? value.requestConcurrency.map((item: unknown) => (typeof item === "number" ? item : 0))
      : [],
    requestDetails: Array.isArray(value.requestDetails)
      ? value.requestDetails.filter(isRecord).map((item) => ({
          url: String(item.url),
          method: String(item.method),
          data: String(item.data),
          headers: isRecord(item.headers) ? item.headers : {},
          status: typeof item.status === "number" ? item.status : null,
          fixtureBytes: typeof item.fixtureBytes === "number" ? item.fixtureBytes : 0,
          finalUrl: typeof item.finalUrl === "string" ? item.finalUrl : String(item.url),
        }))
      : [],
    sourceSha256: typeof value.sourceSha256 === "string" ? value.sourceSha256 : undefined,
    python: typeof value.python === "string" ? value.python : undefined,
    processSeconds: result.elapsed,
    resultRequestCounts: Array.isArray(value.resultRequestCounts)
      ? value.resultRequestCounts.map((value: unknown) => Number(value))
      : [],
    metrics:
      metrics && requiredMetrics.every((key) => typeof metrics[key] === "number")
        ? {
            importSeconds: numeric("importSeconds"),
            firstResultSeconds: nullable("firstResultSeconds"),
            totalSeconds: numeric("totalSeconds"),
            cpuSeconds: numeric("cpuSeconds"),
            responseBytes: numeric("responseBytes"),
            usableResults: numeric("usableResults"),
            peakAllocatedBytes: nullable("peakAllocatedBytes"),
            peakRssBytes: nullable("peakRssBytes"),
          }
        : undefined,
  };
}

export async function replayParserFixture(
  fixture: ParserCase,
  options: ReplayOptions = {},
): Promise<ParserReport> {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-parser-"));
  try {
    const path = resolve(directory, "case.json");
    await Bun.write(path, JSON.stringify(fixture));
    return await replayParserCase(path, options);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

export function usableMagnet(link: string): boolean {
  try {
    return (
      link.startsWith("magnet:?") &&
      new URL(link).searchParams
        .getAll("xt")
        .some((xt) => /^urn:btih:(?:[a-f\d]{40}|[a-z2-7]{32})$/i.test(xt))
    );
  } catch {
    return false;
  }
}

export function assertUsableParserResults(report: ParserReport, allowHttp = false): void {
  if (report.code !== 0 || report.errors.length > 0 || report.records.length === 0) {
    throw new Error(`parser replay failed: ${JSON.stringify(report)}`);
  }
  for (const row of report.records) {
    if (
      typeof row.link !== "string" ||
      (!usableMagnet(row.link) &&
        !(allowHttp && /^https?:\/\//.test(row.link) && new URL(row.link).hostname)) ||
      typeof row.name !== "string" ||
      !row.name.trim() ||
      (typeof row.size !== "string" && typeof row.size !== "number") ||
      typeof row.seeds !== "number" ||
      !Number.isInteger(row.seeds) ||
      typeof row.leech !== "number" ||
      !Number.isInteger(row.leech) ||
      typeof row.engine_url !== "string" ||
      !/^https?:\/\//.test(row.engine_url) ||
      (row.desc_link !== undefined &&
        (typeof row.desc_link !== "string" || !/^https?:\/\//.test(row.desc_link))) ||
      (row.pub_date !== undefined &&
        (typeof row.pub_date !== "number" || !Number.isInteger(row.pub_date)))
    ) {
      throw new Error(`invalid qBittorrent result: ${JSON.stringify(row)}`);
    }
  }
}
