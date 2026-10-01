import { expect, test } from "bun:test";
import { assertUsableParserResults, replayParserFixture as replay } from "./support/parser_replay";

const bit = "https://bitsearch.to";
const magnet = `magnet:?xt=urn:btih:${"A".repeat(40)}&dn=Fixture`;
const secondMagnet = `magnet:?xt=urn:btih:${"B".repeat(40)}`;

interface Card {
  name?: string;
  link?: string;
  size?: string;
  date?: string;
  seeds?: string;
  leech?: string;
}

function bitCard(card: Card): string {
  return `<div class="bg-white"><div class="items-start"><div class="flex-1">
<div class="items-center">${card.name === undefined ? "" : `<a href="https://bitsearch.eu/torrent/fixture">${card.name}</a>`}</div>
<div class="items-center"><span>Video</span><span>${card.size ?? ""}</span><span>${card.date ?? ""}</span></div>
<div class="items-center"><span class="font-medium">${card.seeds ?? ""}</span><span class="font-medium">${card.leech ?? ""}</span></div>
</div><div class="space-y-2">${card.link === undefined ? "" : `<a href="${card.link}">magnet</a>`}</div></div></div>`;
}

function bitPage(cards: Card[], count = 20): string {
  return `<main class="mx-auto">Found <span class="font-semibold">${count}</span><div class="space-y-4">${cards.map(bitCard).join("")}</div></main>`;
}

test("Bitsearch resets card state, skips missing names/magnets, and tolerates optional metadata", async () => {
  const report = await replay({
    plugin: "bitsearch",
    query: "fixture",
    responses: {
      [`${bit}/search?q=fixture&page=1`]: bitPage([
        {
          name: "Complete",
          link: magnet,
          size: "2 GB",
          date: "12/16/2021",
          seeds: "10",
          leech: "2",
        },
        { name: "Missing magnet" },
        { link: secondMagnet },
        { name: "Sparse", link: secondMagnet, date: "invalid", seeds: "unknown" },
      ]),
    },
  });
  assertUsableParserResults(report);
  expect(report.records.length).toBe(2);
  expect(report.records[0]).toMatchObject({
    name: "Complete",
    size: "2GB",
    seeds: 10,
    leech: 2,
    desc_link: "https://bitsearch.eu/torrent/fixture",
  });
  expect(report.records[0].pub_date).toBeGreaterThan(0);
  expect(report.records[1]).toMatchObject({ name: "Sparse", size: "-1", seeds: -1, leech: -1 });
  expect(report.records[1]).not.toHaveProperty("pub_date");
});

test("Bitsearch deduplicates across pages and bounds or stops pagination", async () => {
  const page1 = `${bit}/search?q=fixture&page=1`;
  const page2 = `${bit}/search?q=fixture&page=2`;
  for (const second of [
    bitPage([
      { name: "Duplicate", link: magnet },
      { name: "Second", link: secondMagnet },
    ]),
    "",
  ]) {
    const report = await replay({
      plugin: "bitsearch",
      query: "fixture",
      maxPages: 2,
      responses: { [page1]: bitPage([{ name: "First", link: magnet }], 999), [page2]: second },
    });
    assertUsableParserResults(report);
    expect(report.requests).toEqual(second ? [page1, page2] : [page1, page2, page2, page2]);
    expect(report.records.length).toBe(second ? 2 : 1);
  }
});
