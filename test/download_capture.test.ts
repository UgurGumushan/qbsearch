import { expect, spyOn, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fetchTextWithRetry } from "./live/http";
import { runFunctionalPass } from "./support/parser_capture";
import { replayParserFixture } from "./support/parser_replay";
import { assertTorrentMetadata } from "./support/torrent_metadata";

// A functional pair launches several bounded Python replays. CI runners may
// need longer than Bun's five-second default while static gates run in parallel.
const CAPTURE_TEST_TIMEOUT_MS = 30_000;

const torrent =
  "d4:infod6:lengthi1e4:name4:test12:piece lengthi16384e6:pieces20:aaaaaaaaaaaaaaaaaaaaee";

test("HTTP torrent validation accepts metainfo and rejects HTML, malformed bencoding, and bad lengths", () => {
  expect(() => {
    assertTorrentMetadata(Buffer.from(torrent));
  }).not.toThrow();
  for (const body of [
    "<html>Download torrent</html>",
    "de",
    "d4:infodee",
    torrent + "x",
    torrent.replace("i1e", "i01e"),
    torrent.replace("i1e", "i-1e"),
    torrent.replace("i1e", "i32769e"),
    "l".repeat(101) + "e".repeat(101),
  ]) {
    expect(() => {
      assertTorrentMetadata(Buffer.from(body));
    }).toThrow();
  }
  const v2 =
    "d4:infod9:file treed4:testd0:d6:lengthi1e11:pieces root32:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaeee12:meta versioni2e4:name4:test12:piece lengthi16384eee";
  expect(() => {
    assertTorrentMetadata(Buffer.from(v2));
  }).not.toThrow();
  expect(() => {
    assertTorrentMetadata(Buffer.from(v2.replace("i16384e", "i16385e")));
  }).toThrow();
});

function mockFetch(handler: (url: string) => Response) {
  return spyOn(globalThis, "fetch").mockImplementation(
    Object.assign(
      (input: Parameters<typeof fetch>[0]) =>
        Promise.resolve(handler(input instanceof Request ? input.url : input.toString())),
      { preconnect: globalThis.fetch.preconnect },
    ),
  );
}

test("text capture respects declared Windows-1251 and counts raw bytes", async () => {
  const fetch = mockFetch(
    () =>
      new Response(new Uint8Array([0xcf, 0xf0, 0xe8, 0xe2, 0xe5, 0xf2]), {
        headers: { "content-type": "text/html; charset=cp1251" },
      }),
  );
  try {
    const response = await fetchTextWithRetry("https://example.org");
    expect(response.body).toBe("Привет");
    expect(response.bytes).toBe(6);
  } finally {
    fetch.mockRestore();
  }
});

test("download replay resolves magnets without network and requires separately verified HTTP metadata", async () => {
  const url = "https://pirateiro.io/torrent/test";
  const magnet = `magnet:?xt=urn:btih:${"a".repeat(40)}`;
  const report = await replayParserFixture({
    plugin: "pirateiro",
    query: "inception",
    action: "download",
    detailUrl: url,
    responses: { [url]: `<a href="${magnet}">Download</a>` },
  });
  expect(report.errors).toEqual([]);
  expect(report.output).toEqual([`${magnet} ${url}`]);
  expect(report.downloadRequests).toEqual([]);
  for (const verifiedDownloads of [[], ["https://example.org/test.torrent"]]) {
    const result = await replayParserFixture({
      plugin: "ali213",
      query: "minecraft",
      action: "download",
      detailUrl: "https://example.org/test.torrent",
      responses: {},
      verifiedDownloads,
    });
    expect(result.requests).toEqual([]);
    expect(result.downloadRequests).toEqual(["https://example.org/test.torrent"]);
    expect(result.errors.length).toBe(verifiedDownloads.length ? 0 : 1);
  }
});

function aliResponse(url: string, metadata: Response): Response {
  if (url.includes("/search?"))
    return new Response(
      '<p class="downAddress"><a href="http://down.ali213.net/pcgame/test.html" target="_blank">Download<em>1.2G</em>',
    );
  if (url.endsWith("/pcgame/test.html")) return new Response('var downUrl ="/test"');
  if (url === "http://www.soft50.com/test")
    return new Response('class="result_js" href="https://example.org/detail" target="_blank">');
  if (url === "https://example.org/detail")
    return new Response(
      'id="btbtn" href="http://btfile.soft5566.com/y/test.torrent" target="_blank">',
    );
  if (url.endsWith("/test.torrent")) return metadata;
  throw new Error(`unexpected fetch ${url}`);
}

test(
  "Ali213's real search chain is replayed and both query downloads require verified torrent bytes",
  async () => {
    const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-download-"));
    const requested: string[] = [];
    const fetch = mockFetch((url) => {
      requested.push(url);
      return aliResponse(url, new Response(torrent));
    });
    try {
      const { report } = await runFunctionalPass("ali213", directory);
      expect(report.cases.map((item) => item.error)).toEqual([undefined, undefined]);
      expect(report.clean).toBe(true);
      expect(report.cases.map((item) => item.replay?.records.length)).toEqual([1, 1]);
      for (const item of report.cases)
        expect(item.capture?.downloads[0]).toMatchObject({
          kind: "torrent",
          resolvedUrl: "http://btfile.soft5566.com/y/test.torrent",
        });
      expect(requested.filter((url) => url.endsWith(".torrent"))).toHaveLength(2);
      const paths = await Promise.all(
        report.cases.map(
          async (item) =>
            (
              (await Bun.file(item.capture?.path ?? "missing capture").json()) as {
                metadata: { path: string }[];
              }
            ).metadata[0].path,
        ),
      );
      expect(paths[0]).not.toBe(paths[1]);
    } finally {
      fetch.mockRestore();
      await rm(directory, { recursive: true, force: true });
    }
  },
  CAPTURE_TEST_TIMEOUT_MS,
);

for (const mode of ["magnet", "html", "rate-limited"] as const) {
  test(
    `actual Pirateiro download discovery handles ${mode} without granting false recovery credit`,
    async () => {
      const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-download-failure-"));
      const requested: string[] = [];
      const fetch = mockFetch((url) => {
        requested.push(url);
        if (url.includes("/search?"))
          return new Response(
            "<tr><td><a href='/torrent/1'><h6 class='pt-title'>Fixture</h6></a></td></tr>",
          );
        if (url.endsWith("/torrent/1")) {
          if (mode === "magnet")
            return new Response(
              `<a href='magnet:?xt=urn:btih:${"a".repeat(40)}&amp;dn=Fixture'>Download</a>`,
            );
          if (mode === "rate-limited")
            return new Response(
              new ReadableStream<Uint8Array>({
                start(controller) {
                  controller.error(new Error("interrupted"));
                },
              }),
              { status: 429, headers: { "retry-after": "60" } },
            );
          return new Response("<html>Login to download</html>");
        }
        throw new Error(`unexpected fetch ${url}`);
      });
      try {
        const { report } = await runFunctionalPass("pirateiro", directory);
        expect(report.clean).toBe(mode === "magnet");
        if (mode === "magnet") {
          expect(report.cases[0].capture?.downloads[0].kind).toBe("magnet");
          expect(report.cases[0].capture?.downloads[0].resolvedUrl).toContain("&dn=Fixture");
        } else if (mode === "rate-limited") {
          expect(requested).toHaveLength(3);
          expect(report.cases[0].capture?.responses.at(-1)).toMatchObject({
            status: 429,
            attempts: 1,
            retryAfter: "60",
            bytes: 0,
          });
          expect(report.cases[1].error).toContain("skipped after HTTP 429");
        } else expect(report.cases[0].error).toContain("no usable magnet");
      } finally {
        fetch.mockRestore();
        await rm(directory, { recursive: true, force: true });
      }
    },
    CAPTURE_TEST_TIMEOUT_MS,
  );
}

for (const mode of ["html", "binary-429"] as const) {
  test(
    `HTTP torrent capture rejects ${mode} and preserves its evidence`,
    async () => {
      const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-binary-"));
      const requested: string[] = [];
      const fetch = mockFetch((url) => {
        requested.push(url);
        const metadata =
          mode === "html"
            ? new Response("<html>Download manager</html>")
            : new Response(
                new ReadableStream<Uint8Array>({
                  start(controller) {
                    controller.error(new Error("interrupted metadata"));
                  },
                }),
                { status: 429, headers: { "retry-after": "60" } },
              );
        return aliResponse(url, metadata);
      });
      try {
        const { report } = await runFunctionalPass("ali213", directory);
        expect(report.clean).toBe(false);
        expect(report.cases[0].capture?.downloads).toEqual([]);
        if (mode === "binary-429") {
          expect(requested).toHaveLength(5);
          expect(report.cases[0].capture?.responses.at(-1)).toMatchObject({
            status: 429,
            attempts: 1,
            bytes: 0,
            retryAfter: "60",
          });
          expect(report.cases[1].error).toContain("skipped after HTTP 429");
        } else expect(report.cases[0].error).toContain("invalid bencoded torrent metadata");
      } finally {
        fetch.mockRestore();
        await rm(directory, { recursive: true, force: true });
      }
    },
    CAPTURE_TEST_TIMEOUT_MS,
  );
}
