import { pythonCommand, runCapturedCommand } from "../../tool/core/run";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

export type ParserPlugin =
  "elitetorrent" | "bitsearch" | "solidtorrents" | "ali213" | "pirateiro" | "traht";

export interface ParserCase {
  plugin: ParserPlugin | "audiobookbay" | "darklibria" | "yts";
  query: string;
  category?: string;
  action?: "search" | "detail" | "download";
  detailUrl?: string;
  maxPages?: number;
  maxDetails?: number;
  maxWorkers?: number;
  responses: Record<string, string>;
  sourceSha256?: string;
  verifiedDownloads?: string[];
  responseDelayMs?: number;
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
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** This subprocess consumes saved responses only; it never fetches a site. */
export async function replayParserCase(path: string): Promise<ParserReport> {
  const result = await runCapturedCommand([...pythonCommand(), "-m", "test.parser_harness", path], {
    timeoutSeconds: 10,
  });
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
  };
}

export async function replayParserFixture(fixture: ParserCase): Promise<ParserReport> {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-parser-"));
  try {
    const path = resolve(directory, "case.json");
    await Bun.write(path, JSON.stringify(fixture));
    return await replayParserCase(path);
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
