import { expect, test } from "bun:test";
import { FIXTURES_DIR } from "../tool/core/repo";
import { resolve } from "node:path";
import { replayParserFixture as replay, type ParserCase } from "./support/parser_replay";

const site = "https://pirateiro.io/";
const magnet = `magnet:?xt=urn:btih:${"a".repeat(40)}&dn=A&B`;
function row(id: number, title = `Fixture ${id}`, peers = true): string {
  return `<tr><td>Apps</td><td><a href='/torrent/${id}'><h6 class='pt-title'>${title}</h6></a></td><td>${peers ? "<span class='btn-seed-home badge'>47</span><span class='btn-leech-home'>4</span>" : ""}</td></tr>`;
}

test("Pirateiro's captured desktop rows yield actual titles and peer counts", async () => {
  const fixture = (await Bun.file(
    resolve(FIXTURES_DIR, "parsers", "pirateiro.json"),
  ).json()) as ParserCase;
  const report = await replay(fixture);
  expect(report.errors).toEqual([]);
  expect(report.records).toEqual([
    {
      link: `${site}torrent/354869`,
      desc_link: `${site}torrent/354869`,
      name: "Ubuntu Complete Course",
      size: -1,
      seeds: 54,
      leech: 34,
      engine_url: site,
    },
    {
      link: `${site}torrent/20994`,
      desc_link: `${site}torrent/20994`,
      name: "Ubuntu desktop 19.04 (64bit)",
      size: -1,
      seeds: 47,
      leech: 4,
      engine_url: site,
    },
  ]);
});

test("Pirateiro ignores navigation/mobile cards, decodes titles, and caps unique rows across pages", async () => {
  const report = await replay({
    plugin: "pirateiro",
    query: "fixture",
    maxPages: 2,
    maxDetails: 2,
    responses: {
      [`${site}search?query=fixture&page=1`]: `<a href='${site}'><h6>Navigation</h6></a><div><a href='/torrent/999'><h6 class='pt-title'>Mobile</h6></a></div>${row(1, "A &amp; <b>B</b>", false)}${row(1)}${row(9, " ")}`,
      [`${site}search?query=fixture&page=2`]: row(1) + row(2) + row(3),
    },
  });
  expect(report.errors).toEqual([]);
  expect(report.records).toHaveLength(2);
  expect(report.records[0]).toMatchObject({ name: "A & B", seeds: -1, leech: -1 });
  expect(report.records[1].link).toBe(`${site}torrent/2`);
  expect(report.requests).toHaveLength(2);
});

test("Pirateiro resolves entity-escaped magnets and bounds download-button loops", async () => {
  const detail = `${site}torrent/1`;
  const next = `${site}redirect`;
  const result = await replay({
    plugin: "pirateiro",
    query: "fixture",
    action: "download",
    detailUrl: detail,
    responses: {
      [detail]: `<a href='magnet:?xt=urn:btih:invalid'>bad</a><a class='btn-down' href='/redirect'>Download</a>`,
      [next]: `<a href='${magnet.replaceAll("&", "&amp;")}'>magnet</a>`,
    },
    maxDetails: 2,
  });
  expect(result.errors).toEqual([]);
  expect(result.requests).toEqual([detail, next]);
  expect(result.output).toEqual([`${magnet} ${next}`]);
  const loop = await replay({
    plugin: "pirateiro",
    query: "fixture",
    action: "download",
    detailUrl: detail,
    responses: { [detail]: `<a class='btn-down' href='${detail}'>loop</a>` },
    maxDetails: 2,
  });
  expect(loop.requests).toHaveLength(2);
  expect(loop.errors.join()).toContain("Too many detail redirects");
});

test("Pirateiro's smoke markers count desktop results without navigation or mobile duplicates", async () => {
  const { countResultMarkers } = await import("./live/http");
  expect(
    countResultMarkers(
      `<a href='/torrent/1'><h6 class='pt-title'>Mobile</h6></a>${row(1)}${row(1)}${row(2)}`,
      "text/html",
      { id: "pirateiro", siteUrl: site },
    ),
  ).toBe(2);
});
