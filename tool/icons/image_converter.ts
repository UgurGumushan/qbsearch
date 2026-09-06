import { Image } from "cross-image";

export interface ImageSize {
  width: number;
  height: number;
}

/** Decode an image and return its pixel dimensions. */
export async function inspectImage(data: Uint8Array): Promise<ImageSize> {
  const image = await Image.decode(data);
  return { width: image.width, height: image.height };
}

/**
 * Convert a downloaded favicon to the single-image ICO used by qBittorrent.
 *
 * This mirrors the previous converter: preserve the source aspect ratio on a
 * transparent square canvas, avoid enlarging small images, and downsample
 * larger images to 32x32 with bicubic filtering.
 */
export async function convertToIco(data: Uint8Array): Promise<Uint8Array> {
  const image = await Image.decode(data);
  const side = Math.max(image.width, image.height);
  const canvas = Image.create(side, side, 0, 0, 0, 0);
  canvas.composite(
    image,
    Math.floor((side - image.width) / 2),
    Math.floor((side - image.height) / 2),
  );

  if (side > 32) {
    canvas.resize({ width: 32, height: 32, method: "bicubic" });
  }

  return canvas.encode("ico");
}
