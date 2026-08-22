import { expect, test } from "bun:test";
import { Image } from "cross-image";
import { convertToIco, inspectImage } from "../generate/icons/image_converter";

test("Bun image converter creates a transparent 32px ICO", async () => {
  const source = Image.create(64, 32, 255, 0, 0, 255);
  const sourcePng = await source.encode("png");

  expect(await inspectImage(sourcePng)).toEqual({ width: 64, height: 32 });

  const ico = await convertToIco(sourcePng);
  expect(ico.slice(0, 6)).toEqual(new Uint8Array([0, 0, 1, 0, 1, 0]));

  const decoded = await Image.decode(ico);
  expect([decoded.width, decoded.height]).toEqual([32, 32]);
  expect(decoded.data.slice(0, 4)).toEqual(new Uint8Array([0, 0, 0, 0]));
  expect(decoded.data.slice((16 * 32 + 16) * 4, (16 * 32 + 16) * 4 + 4)).toEqual(
    new Uint8Array([255, 0, 0, 255]),
  );
});
