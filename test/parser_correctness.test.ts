import { expect, test } from "bun:test";
import {
  assertUsableParserResults,
  replayParserFixture as replay,
  type ParserCase,
} from "./support/parser_replay";

function dmhyRow(id: number, date = "2026/10/02", name = "Fixture &amp; &lt;title&gt;"): string {
  return `<tr><td><span>${date}</span><br />12:00</td><td>Anime</td>
<td><a href='topics/view/${id}.html'><b>${name}</b></a></td>
<td><a href='magnet:?xt=urn:btih:${id.toString(16).padStart(40, "0")}&amp;dn=fixture'>Download</a></td>
<td>1&nbsp;GB</td><td><b>12</b></td><td>2</td></tr>`;
}

test("DMHY retains single-quoted links, entities, metadata, and the supplied magnet", async () => {
  const report = await replay({
    plugin: "dmhy",
    query: "fixture",
    responses: {
      "https://share.dmhy.org/topics/list/page/1?keyword=fixture": `<table>${dmhyRow(99)}</table><table id='topic_list'>${dmhyRow(1)}${dmhyRow(1)}</table>`,
    },
  });
  assertUsableParserResults(report, true);
  expect(report.requests).toHaveLength(1);
  expect(report.records).toHaveLength(1);
  expect(report.records[0]).toMatchObject({
    name: "Fixture & <title>",
    link: `magnet:?xt=urn:btih:${"1".padStart(40, "0")}&dn=fixture`,
    desc_link: "https://share.dmhy.org/topics/view/1.html",
    engine_url: "https://share.dmhy.org",
    size: "1 GB",
    seeds: 12,
    leech: 2,
    date: "2026/10/02",
  });
  expect(report.records[0].pub_date).toBeGreaterThan(0);
});

test("DMHY tolerates missing dates and titles and deduplicates across bounded pages", async () => {
  const rows = Array.from({ length: 80 }, () => dmhyRow(1)).join("");
  const report = await replay({
    plugin: "dmhy",
    query: "fixture",
    maxPages: 2,
    responses: {
      "https://share.dmhy.org/topics/list/page/1?keyword=fixture": `<table id='topic_list'>${rows}</table>`,
      "https://share.dmhy.org/topics/list/page/2?keyword=fixture": `<table id='topic_list'>${dmhyRow(1)}${dmhyRow(2, "")}${dmhyRow(3, "2026/10/02", "")}</table>`,
    },
  });
  assertUsableParserResults(report, true);
  expect(report.requests).toHaveLength(2);
  expect(report.records).toHaveLength(2);
  expect(report.records[1].pub_date).toBe(-1);
});

test("DMHY stops printing and pagination at the global result budget", async () => {
  const report = await replay({
    plugin: "dmhy",
    query: "fixture",
    maxPages: 2,
    maxDetails: 3,
    responses: {
      "https://share.dmhy.org/topics/list/page/1?keyword=fixture": `<table id='topic_list'>${Array.from({ length: 80 }, (_, id) => dmhyRow(id + 1)).join("")}</table>`,
    },
  });
  assertUsableParserResults(report, true);
  expect(report.records).toHaveLength(3);
  expect(report.requests).toHaveLength(1);
});

function maxiCase(secondPage: object): ParserCase {
  const url = "http://atomixhq.com";
  return {
    plugin: "maxitorrent",
    query: "fixture",
    maxPages: 2,
    responses: {
      [`${url}/first`]: 'window.location.href = "//files.example/first.torrent";',
      [`${url}/second`]: 'window.location.href = "//files.example/second.torrent";',
    },
    exchanges: [
      {
        url: `${url}/get/result/`,
        method: "POST",
        data: "s=fixture&pg=1",
        response: JSON.stringify({
          data: { torrents: { one: { row: { guid: "first", torrentSize: "1 GB" } } } },
        }),
      },
      {
        url: `${url}/get/result/`,
        method: "POST",
        data: "s=fixture&pg=2",
        response: JSON.stringify(secondPage),
      },
    ],
  };
}

test("Maxitorrent requests consecutive POST pages and reads size before resolving each row", async () => {
  const report = await replay(
    maxiCase({
      data: { torrents: { two: { row: { guid: "second", torrentSize: "2 GB" } } } },
    }),
  );
  assertUsableParserResults(report, true);
  expect(
    report.requestDetails?.filter((request) => request.method === "POST").map((r) => r.data),
  ).toEqual(["s=fixture&pg=1", "s=fixture&pg=2"]);
  expect(report.records.map((row) => row.size)).toEqual(["1 GB", "2 GB"]);
  expect(report.records.map((row) => row.name)).toEqual(["first", "second"]);
  expect(report.records.map((row) => row.link)).toEqual([
    "http://files.example/first.torrent",
    "http://files.example/second.torrent",
  ]);
});

test("Maxitorrent stops on the final page's null slot", async () => {
  const report = await replay(maxiCase({ data: { torrents: { final: null } } }));
  assertUsableParserResults(report, true);
  expect(report.records).toHaveLength(1);
  expect(report.requestDetails?.filter((request) => request.method === "POST")).toHaveLength(2);
});

test("Maxitorrent follows relative detail links and single-quoted redirects without changing hosts", async () => {
  const fixture = maxiCase({ data: { torrents: { final: null } } });
  fixture.responses["http://atomixhq.com/first"] =
    '<span class="color"></span><a href="/redirect">download</a>';
  fixture.responses["http://atomixhq.com/redirect"] =
    "window.location.href='https://files.example/first.torrent?download=1';";
  const report = await replay(fixture);
  assertUsableParserResults(report, true);
  expect(report.records[0].link).toBe("https://files.example/first.torrent?download=1");
  expect(report.requests).toContain("http://atomixhq.com/redirect");
});

test("Maxitorrent stops redirect cycles within the detail budget", async () => {
  const fixture = maxiCase({ data: { torrents: { final: null } } });
  fixture.maxDetails = 2;
  fixture.responses["http://atomixhq.com/first"] = "window.location.href='/redirect';";
  fixture.responses["http://atomixhq.com/redirect"] = "window.location.href='/first';";
  const report = await replay(fixture);
  expect(report.errors).toEqual([]);
  expect(report.records).toEqual([]);
  expect(report.requests.filter((url) => !url.endsWith("/get/result/"))).toEqual([
    "http://atomixhq.com/first",
    "http://atomixhq.com/redirect",
  ]);
});
