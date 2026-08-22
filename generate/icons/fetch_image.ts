import { TIMEOUT_MS, USER_AGENT } from "./constants";
import type { DownloadResult } from "./types";

/** Fetch one candidate image with a bounded request lifetime. */
export async function fetchImage(url: string): Promise<DownloadResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => {
    controller.abort();
  }, TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: controller.signal,
    });
    if (!response.ok) {
      return { data: null, error: `HTTP ${response.status} ${response.statusText}`.trim() };
    }
    const data = new Uint8Array(await response.arrayBuffer());
    return data.byteLength > 0 ? { data, error: null } : { data: null, error: "empty response" };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timeout);
  }
}
