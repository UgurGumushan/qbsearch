import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { ROOT } from "../../tool/core/repo";
import { fetchTextWithRetry } from "../live/http";
import { inspectLivePlugin } from "../live/plugin_contract";
import { elitetorrentResultLinks } from "../live/result_links";
import {
  assertUsableParserResults,
  replayParserCase,
  type ParserCase,
  type ParserPlugin,
  type ParserReport,
} from "./parser_replay";

export const CAPTURE_LIMITS = {
  maxPages: 2,
  maxDetails: 5,
  maxResults: 40,
  maxResponseBytes: 4 * 1024 * 1024,
  timeoutMs: 20_000,
  maxAttempts: 3,
  deadlineMs: 60_000,
} as const;

const FUNCTIONAL_QUERIES: Record<ParserPlugin, readonly string[]> = {
  bitsearch: ["inception", "ubuntu"],
  elitetorrent: ["inception", "matrix"],
  solidtorrents: ["ubuntu", "inception"],
};

interface ResponseEvidence {
  requestedUrl: string;
  finalUrl: string;
  status: number;
  bytes: number;
  attempts: number;
  retryAfter: string | null;
}

interface CapturedCase {
  path: string;
  capturedAt: string;
  responses: ResponseEvidence[];
  sourceSha256: string;
}

class ParserCaptureError extends Error {
  constructor(
    message: string,
    readonly capture: CapturedCase,
  ) {
    super(message);
  }
}

/** Fetch with Bun, then save a complete URL map for a separate offline replay. */
export async function captureParserCase(
  plugin: ParserPlugin,
  query: string,
  directory: string,
): Promise<CapturedCase> {
  const contract = await inspectLivePlugin(resolve(ROOT, "plugins", `${plugin}.py`));
  if (contract.errors.length > 0) {
    throw new Error(contract.errors.join("; "));
  }
  const deadline = performance.now() + CAPTURE_LIMITS.deadlineMs;
  const sourceSha256 = new Bun.CryptoHasher("sha256").update(contract.source).digest("hex");
  const responses: Record<string, string> = {};
  const evidence: ResponseEvidence[] = [];
  await mkdir(directory, { recursive: true });
  const path = resolve(directory, `${plugin}-${encodeURIComponent(query)}.json`);
  let capturedAt = new Date().toISOString();
  const save = async (): Promise<CapturedCase> => {
    capturedAt = new Date().toISOString();
    const fixture: ParserCase = {
      plugin,
      query: encodeURIComponent(query),
      category: "all",
      maxPages: CAPTURE_LIMITS.maxPages,
      maxDetails: plugin === "elitetorrent" ? CAPTURE_LIMITS.maxDetails : CAPTURE_LIMITS.maxResults,
      responses,
      sourceSha256,
    };
    await Bun.write(
      path,
      `${JSON.stringify({ ...fixture, capturedAt, limits: CAPTURE_LIMITS, evidence }, null, 2)}\n`,
    );
    return { path, capturedAt, responses: evidence, sourceSha256 };
  };
  const get = async (url: string): Promise<string> => {
    let response;
    try {
      response = await fetchTextWithRetry(url, { ...CAPTURE_LIMITS, deadline });
    } catch (error) {
      throw new ParserCaptureError(
        error instanceof Error ? error.message : String(error),
        await save(),
      );
    }
    evidence.push({
      requestedUrl: url,
      finalUrl: response.url,
      status: response.status,
      bytes: Buffer.byteLength(response.body),
      attempts: response.attempts,
      retryAfter: response.retryAfter ?? null,
    });
    responses[url] = response.body;
    if (response.status >= 400) {
      const retryAfter =
        response.retryAfter === undefined ? "" : ` (Retry-After: ${response.retryAfter})`;
      throw new ParserCaptureError(`${url}: HTTP ${response.status}${retryAfter}`, await save());
    }
    return response.body;
  };
  const encoded = encodeURIComponent(query).replaceAll("%20", "+");
  const site = contract.siteUrl;
  if (plugin === "bitsearch" || plugin === "solidtorrents") {
    const first = await get(`${site}/search?q=${encoded}&page=1`);
    const count = Number(
      /Found\s+<span[^>]*>(\d+)<\/span>/.exec(first)?.[1] ??
        (plugin === "solidtorrents" ? /<b>(\d+)<\/b>/.exec(first)?.[1] : undefined) ??
        0,
    );
    for (
      let page = 2;
      page <= Math.min(Math.ceil(count / 20), CAPTURE_LIMITS.maxPages);
      page += 1
    ) {
      const html = await get(`${site}/search?q=${encoded}&page=${page}`);
      if (!html) {
        break;
      }
    }
  } else {
    const first = await get(`${site}/?s=${encoded}`);
    let pages = first.includes("Resultado de buscar") ? 1 : 0;
    if (first.includes("paginacion")) {
      const anchors = [...first.matchAll(/<a.*?class="pagina.*?<\/a>/g)];
      pages = Number(anchors.at(-1)?.[0].match(/page\/(\d+)\//)?.[1] ?? 0);
    }
    const details = new Set<string>();
    for (let page = 1; page <= Math.min(pages, CAPTURE_LIMITS.maxPages); page += 1) {
      const html = await get(`${site}/page/${page}/?s=${encoded}`);
      for (const link of elitetorrentResultLinks(html, site)) {
        details.add(link);
        if (details.size === CAPTURE_LIMITS.maxDetails) {
          break;
        }
      }
      if (details.size === CAPTURE_LIMITS.maxDetails) {
        break;
      }
    }
    for (const link of details) {
      await get(link);
    }
  }
  return save();
}

interface FunctionalCase {
  query: string;
  capture?: CapturedCase;
  replay?: ParserReport;
  error?: string;
}

/** A pass is clean only if both fresh queries produce valid actual-engine output. */
export async function runFunctionalPass(
  plugin: ParserPlugin,
  outputRoot = resolve(ROOT, "working", "recovery"),
): Promise<{
  path: string;
  report: {
    plugin: ParserPlugin;
    startedAt: string;
    finishedAt: string;
    localDate: string;
    clean: boolean;
    limits: typeof CAPTURE_LIMITS;
    cases: FunctionalCase[];
  };
}> {
  const startedAt = new Date().toISOString();
  const directory = resolve(outputRoot, `${plugin}-${crypto.randomUUID()}`);
  await mkdir(directory, { recursive: true });
  const cases: FunctionalCase[] = [];
  let rateLimited = false;
  for (const query of FUNCTIONAL_QUERIES[plugin]) {
    const item: FunctionalCase = { query };
    if (rateLimited) {
      item.error = "skipped after HTTP 429; wait for the service's retry window";
      cases.push(item);
      continue;
    }
    try {
      item.capture = await captureParserCase(plugin, query, directory);
      const previousSource = cases.find((previous) => previous.capture !== undefined)?.capture
        ?.sourceSha256;
      if (previousSource !== undefined && previousSource !== item.capture.sourceSha256) {
        throw new Error("plugin source changed between recovery queries");
      }
      item.replay = await replayParserCase(item.capture.path);
      assertUsableParserResults(item.replay);
    } catch (error) {
      if (error instanceof ParserCaptureError) {
        item.capture = error.capture;
        rateLimited = error.capture.responses.some((response) => response.status === 429);
      }
      item.error = error instanceof Error ? error.message : String(error);
    }
    cases.push(item);
  }
  const report = {
    plugin,
    startedAt,
    finishedAt: new Date().toISOString(),
    localDate: new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Istanbul" }).format(new Date()),
    clean: cases.every((item) => item.error === undefined),
    limits: CAPTURE_LIMITS,
    cases,
  };
  const path = resolve(directory, "pass.json");
  await Bun.write(path, `${JSON.stringify(report, null, 2)}\n`);
  return { path, report };
}
