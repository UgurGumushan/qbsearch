import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { expect, test } from "bun:test";
import { FIXTURES_DIR } from "../tool/core/repo";
import { pythonCommand, runCapturedCommand } from "../tool/core/run";
import {
  assertUsableParserResults,
  replayParserCase,
  type ParserCase,
  replayParserFixture as replay,
} from "./support/parser_replay";

const fixtureDir = resolve(FIXTURES_DIR, "parsers");
const elite = "https://www.elitetorrent.com";
const bit = "https://bitsearch.to";
const magnet = `magnet:?xt=urn:btih:${"A".repeat(40)}&dn=Fixture`;

function encodeMagnet(value: string, depth = 1): string {
  const rot13 = value.replace(/[a-z]/gi, (char) => {
    const start = char <= "Z" ? 65 : 97;
    return String.fromCharCode(start + ((char.charCodeAt(0) - start + 13) % 26));
  });
  let result = rot13;
  for (let layer = 0; layer < depth; layer += 1) {
    result = Buffer.from(result).toString("base64");
  }
  return result;
}

function detailCase(anchors: string): ParserCase {
  const url = `${elite}/peliculas/fixture/`;
  return {
    plugin: "elitetorrent",
    query: "fixture",
    action: "detail",
    detailUrl: url,
    responses: {
      [url]: `<h1>Descargar Fixture por torrent</h1><b>Fecha:</b> 2021-12-16 ${anchors}`,
    },
  };
}

for (const name of ["elitetorrent-inception", "elitetorrent-matrix", "bitsearch"]) {
  test(`${name}: captured responses produce the expected actual-engine records`, async () => {
    const path = resolve(fixtureDir, `${name}.json`);
    const fixture = (await Bun.file(path).json()) as ParserCase & {
      expected: Record<string, unknown>[];
    };
    const report = await replayParserCase(path);
    assertUsableParserResults(report);
    expect(report.records.length).toBe(fixture.expected.length);
    const records = [...report.records].sort((a, b) =>
      String(a.desc_link).localeCompare(String(b.desc_link)),
    );
    const expected = [...fixture.expected].sort((a, b) =>
      String(a.desc_link).localeCompare(String(b.desc_link)),
    );
    for (let index = 0; index < records.length; index += 1) {
      expect(records[index]).toMatchObject(expected[index]);
      expect(records[index].pub_date).toBeGreaterThan(0);
    }
    const expectedRequests = Object.keys(fixture.responses).filter(
      (url) => !url.includes("elitetorrent.com/page/1/"),
    );
    expect(new Set(report.requests)).toEqual(new Set(expectedRequests));
  });
}

test("Elitetorrent accepts legacy, reordered, single, and HTML-escaped encoded links", async () => {
  const encoded = encodeURIComponent(encodeMagnet(magnet));
  const torrent = encodeMagnet("https://example.test/file.torrent");
  for (const anchors of [
    `<a href="https://example.test/?i=${encoded}">magnet</a>`,
    `<a href='https://example.test/?i=${encoded}&amp;st=et'>magnet</a>`,
    `<a href=https://example.test/?st=et&i=${encoded}>magnet</a>`,
    `<a href="https://example.test/?i=${encoded}&st=et">magnet</a><a href="https://example.test/?i=${torrent}&st=et">torrent</a>`,
    `<a href="https://example.test/?i=${torrent}&st=et">torrent</a><a href="https://example.test/?st=et&i=${encoded}">magnet</a>`,
  ]) {
    const report = await replay(detailCase(anchors));
    assertUsableParserResults(report);
    expect(report.records[0].link).toBe(magnet);
  }
});

test("Elitetorrent preserves literal and percent-encoded plus signs in legacy Base64", async () => {
  const value = `${magnet}~~~`;
  const encoded = encodeMagnet(value);
  expect(encoded).toContain("+");
  for (const query of [encoded, encodeURIComponent(encoded)]) {
    const report = await replay(
      detailCase(`<a href="https://example.test/?i=${query}&st=et">magnet</a>`),
    );
    expect(report.code).toBe(0);
    expect(report.records[0].link).toBe(value);
  }
});

test("Elitetorrent rejects malformed/non-magnet links and respects its decoding depth", async () => {
  for (const value of [
    "!!!",
    encodeMagnet("https://example.test/magnet"),
    encodeMagnet(magnet, 11),
  ]) {
    const report = await replay(
      detailCase(
        `<a href="https://example.test/?i=${encodeURIComponent(value)}&st=et">download</a>`,
      ),
    );
    expect(report.code).toBe(0);
    expect(report.errors).toEqual([]);
    expect(report.records).toEqual([]);
  }
  const report = await replay(
    detailCase(
      `<a href="https://example.test/?i=${encodeURIComponent(encodeMagnet(magnet, 10))}">download</a>`,
    ),
  );
  expect(report.records[0].link).toBe(magnet);
});

test("Elitetorrent filters categories, deduplicates details, and obeys both work caps", async () => {
  const movie = `${elite}/peliculas/movie/`;
  const tv = `${elite}/series/show/`;
  const extra = `${elite}/peliculas/extra/`;
  const detail = detailCase(
    `<a href="https://example.test/?i=${encodeURIComponent(encodeMagnet(magnet))}&st=et">magnet</a>`,
  ).responses[`${elite}/peliculas/fixture/`];
  const listing = `paginacion <a class="pagina" href="${elite}/page/99/">99</a><a href="${movie}">movie</a><a href="${movie}">image</a><a href="${tv}">tv</a><a href="${extra}">extra</a>`;
  for (const category of ["all", "movies", "tv"]) {
    const fixture: ParserCase = {
      plugin: "elitetorrent",
      query: "fixture",
      category,
      maxPages: 1,
      maxDetails: 1,
      responses: {
        [`${elite}/?s=fixture`]: listing,
        [`${elite}/page/1/?s=fixture`]: listing,
        [category === "tv" ? tv : movie]: detail,
      },
    };
    const report = await replay(fixture);
    assertUsableParserResults(report);
    expect(report.records.length).toBe(1);
    expect(report.requests.length).toBe(2);
    expect(report.records[0].desc_link).toBe(category === "tv" ? tv : movie);
  }
});

test("offline replay fails on unexpected requests instead of quietly accepting empty results", async () => {
  const report = await replay({ plugin: "bitsearch", query: "fixture", responses: {} });
  expect(report.code).toBe(1);
  expect(report.errors).toEqual(
    Array<string>(3).fill(`unexpected request: ${bit}/search?q=fixture&page=1`),
  );
});

test("offline replay rejects captures from a different plugin source revision", async () => {
  const fixture = detailCase("");
  fixture.sourceSha256 = "stale";
  const report = await replay(fixture);
  expect(report.code).toBe(1);
  expect(report.requests).toEqual([]);
  expect(report.errors).toEqual(["ValueError: plugin source changed after response capture"]);
});

test("offline replay blocks real network and download calls", async () => {
  const dir = await mkdtemp(resolve(tmpdir(), "qbsearch-network-guard-"));
  try {
    const path = resolve(dir, "case.json");
    await Bun.write(path, JSON.stringify({ plugin: "elitetorrent", responses: {} }));
    await Bun.write(
      resolve(dir, "plugins", "elitetorrent.py"),
      `import socket
from urllib.request import urlopen
from helpers import download_file
class elitetorrent:
    def search(self, what, cat):
        for operation in (lambda: socket.create_connection(("example.test", 443)), lambda: urlopen("https://example.test"), lambda: download_file("https://example.test")):
            try:
                operation()
            except RuntimeError:
                pass
`,
    );
    const script = `import json, sys
from pathlib import Path
from test import parser_harness
parser_harness.__file__ = str(Path(sys.argv[1]) / "test" / "parser_harness.py")
print(json.dumps(parser_harness.replay(Path(sys.argv[1]) / "case.json")))`;
    const result = await runCapturedCommand([...pythonCommand(), "-c", script, dir], {
      timeoutSeconds: 10,
    });
    expect(result.code).toBe(0);
    const report = JSON.parse(result.output) as { errors: string[] };
    expect(report.errors).toEqual([
      "network or download attempted during offline replay",
      "unexpected request: https://example.test",
      "network or download attempted during offline replay",
    ]);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
