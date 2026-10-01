import { expect, test } from "bun:test";
import { resolve } from "node:path";
import { FIXTURES_DIR } from "../tool/core/repo";
import {
  assertUsableParserResults,
  replayParserCase,
  replayParserFixture as replay,
  type ParserCase,
} from "./support/parser_replay";

const site = "https://solidtorrents.to";
const firstMagnet = `magnet:?xt=urn:btih:${"A".repeat(40)}&dn=Fixture`;
const secondMagnet = `magnet:?xt=urn:btih:${"B".repeat(40)}`;
const page1 = `${site}/search?q=fixture&page=1`;
const page2 = `${site}/search?q=fixture&page=2`;

interface Card {
  name?: string;
  link?: string;
  href?: string;
  size?: string;
  seeds?: string;
  leech?: string;
  date?: string;
}

function modernCard(card: Card): string {
  const link = card.link?.replaceAll("&", "&amp;").replaceAll("=", "&#x3D;");
  const magnet = link === undefined ? "" : `<a href="${link}">magnet</a>`;
  return `<div class="bg-white"><div class="items-start"><div class="flex-1">
<div class="items-center"><h3><div class="bg-white">${card.name === undefined ? "" : `<a href="${card.href ?? "/torrent/fixture"}">${card.name}</a>`}</div></h3></div>
<div class="items-center"><span><i></i><span>Video</span></span><span><i></i><span>${card.size ?? ""}</span></span><span><i></i><span>${card.date ?? ""}</span></span></div>
<div class="items-center"><span><span class="font-medium">${card.seeds ?? ""}</span>seeders</span><span><span class="font-medium">${card.leech ?? ""}</span>leechers</span></div>
</div><div class="space-y-2">${magnet}</div></div><div class="sm:hidden">${magnet}</div></div>`;
}

function modernPage(cards: Card[], count = 20): string {
  return `<main class="mx-auto">Found <span class="font-semibold">${count}</span><div class="space-y-4">${cards.map(modernCard).join("")}</div></main>`;
}

function legacyCard(card: Card): string {
  return `<li class="search-result"><div class="info"><h5>${card.name === undefined ? "" : `<a href="${card.href ?? "/view/fixture"}">${card.name}</a>`}</h5>
<div class="stats"><div>Video</div><div>${card.size ?? ""}</div><div>${card.seeds ?? ""}</div><div>${card.leech ?? ""}</div><div>${card.date ?? ""}</div></div></div>
<div class="links">${card.link === undefined ? "" : `<a class="dl-magnet" href="${card.link}">magnet</a>`}</div></li>`;
}

test("Solid Torrents replays captured redirected pages with complete expected metadata", async () => {
  const path = resolve(FIXTURES_DIR, "parsers", "solidtorrents.json");
  const fixture = (await Bun.file(path).json()) as ParserCase & {
    expected: Record<string, unknown>[];
  };
  const report = await replayParserCase(path);
  assertUsableParserResults(report);
  expect(report.records).toEqual(fixture.expected);
  expect(report.requests).toEqual(Object.keys(fixture.responses));
  expect(report.records.every((row) => row.engine_url === site)).toBe(true);
});

test("Solid Torrents resets cards, reads nested names, and rejects incomplete results", async () => {
  const report = await replay({
    plugin: "solidtorrents",
    query: "fixture",
    responses: {
      [page1]: modernPage([
        {
          name: "Complete <strong>result</strong>",
          link: firstMagnet,
          href: "https://bitsearch.eu/torrent/fixture",
          size: "2 GB",
          seeds: "10",
          leech: "2",
          date: "12/16/2021",
        },
        { name: "Missing magnet" },
        { link: secondMagnet },
        { name: "Bad scheme", link: "https://example.test/not-a-magnet" },
        { name: "Sparse", link: secondMagnet, date: "invalid", seeds: "unknown" },
      ]),
    },
  });
  assertUsableParserResults(report);
  expect(report.records).toHaveLength(2);
  expect(report.records[0]).toMatchObject({
    name: "Complete result",
    link: firstMagnet,
    size: "2GB",
    seeds: 10,
    leech: 2,
    desc_link: "https://bitsearch.eu/torrent/fixture",
    pub_date: 1639612800,
  });
  expect(report.records[1]).toMatchObject({
    name: "Sparse",
    size: "-1",
    seeds: -1,
    leech: -1,
    desc_link: `${site}/torrent/fixture`,
  });
  expect(report.records[1]).not.toHaveProperty("pub_date");
});

test("Solid Torrents retains legacy cards and UTC dates without leaking row state", async () => {
  const report = await replay({
    plugin: "solidtorrents",
    query: "fixture",
    responses: {
      [page1]: `<b>20</b><ul>${[
        {
          name: "Legacy <strong>result</strong>",
          link: firstMagnet,
          size: "1 GB",
          seeds: "3",
          leech: "1",
          date: "Dec 16, 2021",
        },
        { link: secondMagnet },
        { name: "Legacy sparse", link: secondMagnet, date: "invalid" },
      ]
        .map(legacyCard)
        .join("")}</ul>`,
    },
  });
  assertUsableParserResults(report);
  expect(report.records).toHaveLength(2);
  expect(report.records[0]).toMatchObject({
    name: "Legacy result",
    size: "1GB",
    seeds: 3,
    leech: 1,
    desc_link: `${site}/view/fixture`,
    pub_date: 1639612800,
  });
  expect(report.records[1]).toMatchObject({ name: "Legacy sparse", size: "-1", seeds: -1 });
  expect(report.records[1]).not.toHaveProperty("pub_date");
});

test("Solid Torrents bounds pages and results and deduplicates across pages", async () => {
  const fixture: ParserCase = {
    plugin: "solidtorrents",
    query: "fixture",
    maxPages: 2,
    responses: {
      [page1]: modernPage([{ name: "First", link: firstMagnet }], 999),
      [page2]: modernPage([
        { name: "Duplicate", link: firstMagnet },
        { name: "Second", link: secondMagnet },
      ]),
    },
  };
  const report = await replay(fixture);
  assertUsableParserResults(report);
  expect(report.records.map((row) => row.name)).toEqual(["First", "Second"]);
  expect(report.requests).toEqual([page1, page2]);
  for (const limits of [{ maxPages: 1 }, { maxDetails: 1 }]) {
    const bounded = await replay({ ...fixture, ...limits });
    assertUsableParserResults(bounded);
    expect(bounded.records).toHaveLength(1);
    expect(bounded.requests).toEqual([page1]);
  }
  const empty = await replay({ ...fixture, responses: { ...fixture.responses, [page2]: "" } });
  assertUsableParserResults(empty);
  expect(empty.records).toHaveLength(1);
  expect(empty.requests).toEqual([page1, page2, page2, page2]);
});

test("Solid Torrents ignores cards outside result lists and exact class tokens", async () => {
  const decoy = modernCard({ name: "Sidebar", link: secondMagnet });
  const report = await replay({
    plugin: "solidtorrents",
    query: "fixture",
    responses: {
      [page1]: `<main class="mx-auto">Found <span>20</span>${decoy}<div class="not-space-y-4">${decoy}</div><div class="space-y-4">${modernCard({ name: "Actual", link: firstMagnet })}</div></main>`,
    },
  });
  assertUsableParserResults(report);
  expect(report.records.map((row) => row.name)).toEqual(["Actual"]);
});

test("Solid Torrents stops cleanly on empty results or a challenge page", async () => {
  for (const html of [modernPage([], 0), "<html><p>Challenge</p></html>"]) {
    const report = await replay({
      plugin: "solidtorrents",
      query: "fixture",
      responses: { [page1]: html },
    });
    expect(report.code).toBe(0);
    expect(report.errors).toEqual([]);
    expect(report.records).toEqual([]);
    expect(report.requests).toEqual([page1]);
  }
});
