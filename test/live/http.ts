import type { LiveResponse } from "./types";
import { elitetorrentResultLinks } from "./result_links";

const LIVE_REQUEST_TIMEOUT_MS = 20_000;
const DEFAULT_ATTEMPTS = 3;
const RETRYABLE_STATUS = new Set([408, 425, 500, 502, 503, 504]);
const LIVE_HEADERS = {
  accept: "text/html,application/json;q=0.9,*/*;q=0.8",
  "accept-language": "en-US,en;q=0.9",
  "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
};

export interface FetchOptions {
  timeoutMs?: number;
  maxAttempts?: number;
  onRequest?: () => void;
  maxResponseBytes?: number;
  deadline?: number;
}

async function readText(response: Response, limit?: number): Promise<string> {
  if (limit === undefined) {
    return response.text();
  }
  if (!response.body) {
    return "";
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const chunks: string[] = [];
  let size = 0;
  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) {
        break;
      }
      size += chunk.value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new RangeError(`response exceeds ${limit} bytes`);
      }
      chunks.push(decoder.decode(chunk.value, { stream: true }));
    }
    chunks.push(decoder.decode());
    return chunks.join("");
  } finally {
    reader.releaseLock();
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function fetchTextWithRetry(
  url: string,
  options: FetchOptions = {},
): Promise<LiveResponse> {
  const timeoutMs = options.timeoutMs ?? LIVE_REQUEST_TIMEOUT_MS;
  const maxAttempts = Math.max(1, options.maxAttempts ?? DEFAULT_ATTEMPTS);
  let lastError: unknown = null;
  const pause = async (attempt: number): Promise<void> => {
    const remaining = options.deadline === undefined ? 1_000 : options.deadline - performance.now();
    await Bun.sleep(Math.max(0, Math.ceil(Math.min(250 * attempt, 1_000, remaining))));
  };

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const remaining =
      options.deadline === undefined ? timeoutMs : options.deadline - performance.now();
    if (remaining <= 0) {
      throw new Error("capture deadline exceeded");
    }
    options.onRequest?.();
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        controller.abort();
      },
      Math.min(timeoutMs, remaining),
    );
    try {
      const response = await fetch(url, {
        headers: LIVE_HEADERS,
        redirect: "follow",
        signal: controller.signal,
      });
      let body = "";
      try {
        body = await readText(response, options.maxResponseBytes);
      } catch (error) {
        // A known rate limit still stops requests when its body cannot be read.
        if (response.status !== 429) {
          throw error;
        }
      }
      if (RETRYABLE_STATUS.has(response.status) && attempt < maxAttempts) {
        await pause(attempt);
        continue;
      }
      return {
        url: response.url || url,
        status: response.status,
        body,
        contentType: response.headers.get("content-type") ?? "",
        attempts: attempt,
        retryAfter: response.headers.get("retry-after") ?? undefined,
      };
    } catch (error) {
      if (error instanceof RangeError) {
        throw error;
      }
      lastError = error;
      if (attempt < maxAttempts) {
        await pause(attempt);
        continue;
      }
    } finally {
      clearTimeout(timer);
    }
  }

  const detail = lastError instanceof Error ? lastError.message : String(lastError);
  throw new Error(`request failed after ${maxAttempts} attempts: ${detail}`);
}

function countJsonResultMarkers(value: unknown): number {
  if (Array.isArray(value)) {
    return value.length;
  }
  if (!isRecord(value)) {
    return 0;
  }
  if (Object.hasOwn(value, "link") || Object.hasOwn(value, "magnet_uri")) {
    return 1;
  }
  let largest = 0;
  for (const [key, child] of Object.entries(value)) {
    if (/result|torrent|movie|item|release|entry|data|rows/i.test(key)) {
      largest = Math.max(largest, countJsonResultMarkers(child));
    }
  }
  return largest;
}

export function countResultMarkers(
  body: string,
  contentType = "",
  plugin?: { id: string; siteUrl: string },
): number {
  if (/json/i.test(contentType) || /^(?:\[|\{)/.test(body.trim())) {
    try {
      return countJsonResultMarkers(JSON.parse(body) as unknown);
    } catch {
      // Fall through to the HTML/text marker scan for challenge pages or
      // incorrectly labelled responses.
    }
  }

  if (plugin?.id === "elitetorrent") {
    return elitetorrentResultLinks(body, plugin.siteUrl).length;
  }

  const patterns = [
    /href\s*=\s*["'][^"']*magnet:/gi,
    /href\s*=\s*["'][^"']*\.torrent(?:[?#]|["'])/gi,
    /class\s*=\s*["'][^"']*(?:torrent|result|release|search-result|download)[^"']*["']/gi,
    /<article\b/gi,
  ];
  return Math.max(...patterns.map((pattern) => body.match(pattern)?.length ?? 0), 0);
}
