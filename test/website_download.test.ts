/**
 * Verify static website downloads resolve through the stable release contract.
 * @file
 */
import { expect, test } from "bun:test";
import { resolve } from "node:path";
import { ROOT } from "../tool/core/repo";

const SITE = resolve(ROOT, "packages", "website");
const DOWNLOAD =
  "https://github.com/UgurGumushan/qbsearch/releases/latest/download/qbsearch-latest.zip";

test("the static page and legacy redirect share the stable release download", async () => {
  const config = (await Bun.file(resolve(SITE, "vercel.json")).json()) as {
    outputDirectory: string;
    redirects: { source: string; destination: string; permanent: boolean }[];
  };
  expect(config.redirects.find((redirect) => redirect.source === "/download/latest")).toEqual({
    source: "/download/latest",
    destination: DOWNLOAD,
    permanent: false,
  });
  const html = await Bun.file(resolve(SITE, config.outputDirectory, "index.html")).text();
  const downloads: string[] = [];
  const assets: string[] = [];
  let scripts = 0;
  await new HTMLRewriter()
    .on("a.download-button", {
      /** Collect the matched HTML element for static download-contract assertions. */
      element(element) {
        downloads.push(element.getAttribute("href") ?? "");
      },
    })
    .on("link[href]", {
      /** Collect the matched HTML element for static download-contract assertions. */
      element(element) {
        assets.push(element.getAttribute("href") ?? "");
      },
    })
    .on("script", {
      /** Collect the matched HTML element for static download-contract assertions. */
      element() {
        scripts += 1;
      },
    })
    .transform(new Response(html))
    .text();
  expect(downloads).toEqual([DOWNLOAD]);
  expect(scripts).toBe(0);
  expect(assets).toHaveLength(2);
  for (const asset of assets) {
    expect(asset.startsWith("/")).toBe(true);
    expect(await Bun.file(resolve(SITE, config.outputDirectory, asset.slice(1))).exists()).toBe(
      true,
    );
  }
});
