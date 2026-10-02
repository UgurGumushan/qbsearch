import { expect, test } from "bun:test";
import { gzipSync } from "node:zlib";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { runCommandLine } from "../tool/cli";
import { pythonCommand, runCapturedCommand } from "../tool/core/run";
import { academicCase, benchmarkFixtures, darkWideCase, unionCase } from "./performance/fixtures";
import { parseBenchmarkArguments } from "./performance/runner";
import { acceptance, distribution, resultSignature, summarize } from "./performance/statistics";
import {
  replayParserFixture as replay,
  assertUsableParserResults,
  type ParserReport,
} from "./support/parser_replay";

test("benchmark flags validate values and reject live/watch combinations", async () => {
  expect(parseBenchmarkArguments([])).toMatchObject({
    baseline: "v0.1.10",
    samples: 20,
    warmups: 2,
    matrix: false,
  });
  expect(parseBenchmarkArguments(["--plugin", "yts", "--matrix", "--samples", "1"])).toMatchObject({
    plugins: ["yts"],
    matrix: true,
    samples: 1,
  });
  for (const args of [
    ["--plugin"],
    ["--samples", "0"],
    ["--warmups", "-1"],
    ["--live"],
    ["--baseline", "--matrix"],
  ]) {
    expect(() => parseBenchmarkArguments(args)).toThrow();
  }
  expect(await runCommandLine(["test", "--benchmark", "--live"])).toBe(2);
  expect(await runCommandLine(["test", "--benchmark", "--watch"])).toBe(2);
});

test("benchmark statistics use medians and nearest-rank p95; empty first result stays null", () => {
  expect(distribution([4, 1, 2, 3])).toEqual({ median: 2.5, p95: 4 });
  expect(distribution([])).toBeNull();
  const report: ParserReport = {
    code: 0,
    records: [],
    requests: [],
    errors: [],
    downloadRequests: [],
    output: [],
    metrics: {
      importSeconds: 1,
      firstResultSeconds: null,
      totalSeconds: 2,
      cpuSeconds: 0.003,
      responseBytes: 0,
      usableResults: 0,
      peakAllocatedBytes: 100,
      peakRssBytes: 1000,
    },
  };
  const before = summarize([report], [report]);
  const after = summarize(
    [
      {
        ...report,
        metrics: {
          importSeconds: 1,
          firstResultSeconds: null,
          totalSeconds: 1.7,
          cpuSeconds: 0.001,
          responseBytes: 0,
          usableResults: 0,
          peakAllocatedBytes: 100,
          peakRssBytes: 1000,
        },
      },
    ],
    [report],
  );
  expect(before.first).toBeNull();
  expect(acceptance(before, after).wins).toEqual(["total >=10%"]);
  expect(acceptance(after, before).regressions).toEqual(["total median >5%", "total p95 >10%"]);
  expect(resultSignature({ ...report, records: [{ a: 1, b: 2 }, { b: 3 }] }, false)).toBe(
    resultSignature({ ...report, records: [{ b: 3 }, { b: 2, a: 1 }] }, false),
  );
  expect(resultSignature({ ...report, records: [{ a: 1 }, { a: 2 }] }, true)).not.toBe(
    resultSignature({ ...report, records: [{ a: 2 }, { a: 1 }] }, true),
  );
});

test("offline transport matches POST bodies, custom openers, binary responses, redirects and errors", async () => {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-transport-"));
  const url = "https://example.test/api";
  try {
    await Bun.write(
      resolve(directory, "plugins", "elitetorrent.py"),
      `import gzip
from pathlib import Path
from urllib.request import Request, build_opener, urlopen
from urllib.error import HTTPError
from novaprinter import prettyPrinter
Path(__file__).with_name("cookie.txt").write_text("isolated")
Path.home().mkdir(parents=True, exist_ok=True)
Path.home().joinpath("cache.txt").write_text("isolated")
class elitetorrent:
    def search(self, what, cat):
        names = []
        with urlopen("${url}") as response:
            names.append(gzip.decompress(response.read()).decode())
        with urlopen("${url}", data=b"one") as response:
            names.append(response.read().decode())
        opener = build_opener()
        opener.addheaders = [("X-Fixture", "yes")]
        with opener.open("${url}", data=b"two") as response:
            names.append(response.read().decode() + response.geturl())
        try:
            urlopen(Request("https://example.test/missing"))
        except HTTPError as error:
            names.append(str(error.code))
        for name in names:
            prettyPrinter({"name": name, "link": "magnet:?xt=urn:btih:${"a".repeat(40)}", "size": "1 GB", "seeds": 10, "leech": 2, "engine_url": "https://example.test"})
`,
    );
    const report = await replay(
      {
        plugin: "elitetorrent",
        query: "fixture",
        responses: {},
        exchanges: [
          {
            url,
            method: "GET",
            response: {
              bodyBase64: gzipSync("binary").toString("base64"),
              headers: { "Content-Encoding": "gzip" },
            },
          },
          { url, method: "POST", data: "one", response: "first" },
          {
            url,
            method: "POST",
            data: "two",
            response: { body: "second ", finalUrl: "https://example.test/redirected" },
          },
          { url: "https://example.test/missing", method: "GET", response: { status: 404 } },
        ],
      },
      { sourceRoot: directory, measure: true, trace: true },
    );
    assertUsableParserResults(report);
    expect(report.records.map((row) => row.name)).toEqual([
      "binary",
      "first",
      "second https://example.test/redirected",
      "404",
    ]);
    expect(report.requestDetails?.map((item) => [item.method, item.data])).toEqual([
      ["GET", ""],
      ["POST", "one"],
      ["POST", "two"],
      ["GET", ""],
    ]);
    expect(report.requestDetails?.[2].headers).toEqual({ "X-fixture": "yes" });
    expect(report.requestDetails?.map((item) => item.status)).toEqual([200, 200, 200, 404]);
    expect(report.metrics?.usableResults).toBe(4);
    expect(report.metrics?.firstResultSeconds).toBeGreaterThan(0);
    expect(report.metrics?.peakAllocatedBytes).toBeGreaterThan(0);
    expect(await Bun.file(resolve(directory, "plugins", "cookie.txt")).exists()).toBe(false);
    expect(await Bun.file(resolve(directory, "home", "cache.txt")).exists()).toBe(false);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("offline transport rejects unmatched POST bodies even when a legacy GET fixture exists", async () => {
  const result = await runCapturedCommand([
    ...pythonCommand(),
    "-c",
    `from test.replay_transport import FixtureTransport
errors = []
transport = FixtureTransport({"responses": {"https://example.test": "get"}, "exchanges": [{"url": "https://example.test", "method": "POST", "data": "expected", "response": "post"}]}, errors)
for body in (b"unexpected", b"\\xff"):
    try:
        transport.urlopen("https://example.test", data=body)
        raise AssertionError("unmatched body was accepted")
    except RuntimeError:
        pass
assert len(errors) == 2 and transport.active == 0
response = transport.urlopen("https://example.test")
assert response.read(1) == b"g" and transport.active == 1
assert response.read() == b"et" and transport.active == 0
assert response.read() == b""
response.close()
assert transport.active == 0
print("strict transport and EOF accounting preserved")`,
  ]);
  expect(result.code).toBe(0);
  expect(result.output).toBe("strict transport and EOF accounting preserved");
});

test("offline replay exercises a zero deadline and stops detail work", async () => {
  const fixture = (await benchmarkFixtures("elitetorrent"))[0].case;
  const report = await replay({ ...fixture, deadlineMs: 0 });
  expect(report.errors).toEqual([]);
  expect(report.records).toEqual([]);
  expect(report.requests).toEqual(["https://www.elitetorrent.com/?s=inception"]);
});

test("AcademicTorrents selects cached rows and rejects a malformed tail before any detail requests", async () => {
  const fixture = academicCase(1000, 3);
  const report = await replay(fixture);
  assertUsableParserResults(report, true);
  expect(report.records.map((row) => row.name).sort()).toEqual([
    "fixture dataset 0",
    "fixture dataset 1",
    "fixture dataset 2",
  ]);
  expect(report.requests.length).toBe(3);
  const invalid = await replay({ ...fixture, cacheXml: `${fixture.cacheXml ?? ""}<truncated` });
  expect(invalid.errors).toEqual([]);
  expect(invalid.records).toEqual([]);
  expect(invalid.requests).toEqual([]);
});

test("Darklibria wide DOM preserves usable result metadata", async () => {
  const report = await replay(darkWideCase(100));
  assertUsableParserResults(report);
  expect(report.records.length).toBe(32);
  expect(report.requests.length).toBe(34);
});

test("Darklibria DOM keeps tuple content snapshots and malformed/self-closing HTML semantics", async () => {
  const result = await runCapturedCommand([
    ...pythonCommand(),
    "-c",
    `import logging
logging.getLogger().addHandler(logging.NullHandler())
from test.engine_harness import load_qbitt_modules
load_qbitt_modules(prefer_profile=False)
from plugins.darklibria import Parser, Tag
tree = Parser('<div id="outer">A<b>B</b>C<br><i>D</i></div>')
outer = tree.find("div")
assert outer is not None and outer.text == "ABCD"
assert [node.type for node in outer.children] == ["b", "br", "i"]
assert outer.find("br").is_self_closing is True
assert outer.attrs == {"id": "outer"}
tag = Tag("p")
tag.add_content("one")
snapshot = tag.content
tag.add_content("two")
assert isinstance(snapshot, tuple) and snapshot == ("one",)
assert tag.content == ("one", "two")
assert Parser('<p>one<b>two').text == "onetwo"
print("DOM semantics preserved")`,
  ]);
  expect(result.code).toBe(0);
  expect(result.output).toBe("DOM semantics preserved");
});

test("positive UnionDHT fixture executes the real parser; unknown engines are explicitly unverified", async () => {
  const report = await replay(unionCase());
  expect(report.code).toBe(0);
  expect(report.records.length).toBe(10);
  expect(report.requests.length).toBe(5);
  expect(report.resultRequestCounts).toEqual([1, 1, 2, 2, 3, 3, 4, 4, 5, 5]);
  expect((await benchmarkFixtures("dmhy"))[0].evidence).toBe("empty");
});
