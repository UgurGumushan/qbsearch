import type { ImageSize } from "./image_converter";

export interface ManifestEntry {
  url: string | null;
  host: string;
  ico: string;
  ok: boolean;
  error: string | null;
  source: string | null;
}

export type Manifest = Partial<Record<string, ManifestEntry>>;

export interface DownloadResult {
  data: Uint8Array | null;
  error: string | null;
}

export interface Candidate {
  data: Uint8Array;
  source: string;
  size: ImageSize;
}
