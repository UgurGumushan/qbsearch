import { inspectImage } from "./image_converter";
import { fetchImage } from "./fetch_image";
import type { Candidate } from "./types";

/** Download and decode one icon candidate, appending a human-readable error. */
export async function loadCandidate(
  source: string,
  url: string,
  errors: string[],
): Promise<Candidate | null> {
  const downloaded = await fetchImage(url);
  if (downloaded.error !== null) {
    errors.push(`${source}: ${downloaded.error}`);
    return null;
  }
  if (downloaded.data === null) {
    errors.push(`${source}: empty response`);
    return null;
  }

  try {
    const size = await inspectImage(downloaded.data);
    return { data: downloaded.data, source, size };
  } catch (error) {
    errors.push(
      `${source}: not an image (${error instanceof Error ? error.message : String(error)})`,
    );
    return null;
  }
}
