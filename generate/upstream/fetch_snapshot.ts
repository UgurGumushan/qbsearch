import { basename } from "node:path";
import { CONNECT_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from "./constants";

export function pluginStem(url: string): string {
  return basename(new URL(url).pathname, ".py");
}

/** Download one upstream snapshot without allowing a hung host to block a run. */
export async function fetchSnapshot(url: string, outputPath: string): Promise<boolean> {
  const controller = new AbortController();
  const connectTimeout = setTimeout(() => {
    controller.abort();
  }, CONNECT_TIMEOUT_MS);
  const requestTimeout = setTimeout(() => {
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(connectTimeout);
    if (!response.ok) {
      return false;
    }
    const content = new Uint8Array(await response.arrayBuffer());
    if (content.byteLength === 0) {
      return false;
    }
    await Bun.write(outputPath, content);
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(connectTimeout);
    clearTimeout(requestTimeout);
  }
}
