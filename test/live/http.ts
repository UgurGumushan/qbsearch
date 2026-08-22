import type { LiveResponse } from "./types";

const LIVE_REQUEST_TIMEOUT_MS = 20_000;
const DEFAULT_ATTEMPTS = 3;
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const LIVE_HEADERS = {
  accept: "text/html,application/json;q=0.9,*/*;q=0.8",
  "accept-language": "en-US,en;q=0.9",
  "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
};

export interface FetchOptions {
  timeoutMs?: number;
  maxAttempts?: number;
  onRequest?: () => void;
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

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    options.onRequest?.();
    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);
    try {
      const response = await fetch(url, {
        headers: LIVE_HEADERS,
        redirect: "follow",
        signal: controller.signal,
      });
      const body = await response.text();
      if (RETRYABLE_STATUS.has(response.status) && attempt < maxAttempts) {
        await Bun.sleep(Math.min(250 * attempt, 1_000));
        continue;
      }
      return {
        url: response.url || url,
        status: response.status,
        body,
        contentType: response.headers.get("content-type") ?? "",
        attempts: attempt,
      };
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await Bun.sleep(Math.min(250 * attempt, 1_000));
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

export function countResultMarkers(body: string, contentType = ""): number {
  if (/json/i.test(contentType) || /^(?:\[|\{)/.test(body.trim())) {
    try {
      return countJsonResultMarkers(JSON.parse(body) as unknown);
    } catch {
      // Fall through to the HTML/text marker scan for challenge pages or
      // incorrectly labelled responses.
    }
  }

  const patterns = [
    /href\s*=\s*["'][^"']*magnet:/gi,
    /href\s*=\s*["'][^"']*\.torrent(?:[?#]|["'])/gi,
    /class\s*=\s*["'][^"']*(?:torrent|result|release|search-result|download)[^"']*["']/gi,
    /<article\b/gi,
  ];
  return Math.max(...patterns.map((pattern) => body.match(pattern)?.length ?? 0), 0);
}
