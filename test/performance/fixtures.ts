import { resolve } from "node:path";
import { FIXTURES_DIR } from "../../tool/core/repo";
import { audiobookCase, darklibriaCase, ytsCase } from "../support/concurrent_cases";
import type { ParserCase } from "../support/parser_replay";

export interface BenchmarkFixture {
  name: string;
  evidence: "capture" | "synthetic" | "empty";
  ordered: boolean;
  case: ParserCase;
}

export function academicCase(items = 10000, matched = 5): ParserCase {
  const site = "https://academictorrents.com/";
  const responses: Record<string, string> = {};
  const rows = Array.from({ length: items }, (_, id) => {
    const hash = (id + 1).toString(16).padStart(40, "0");
    if (id < matched) {
      responses[`${site}details/${id}/tech`] = "Mirrors: 10<br />2<br />Added: 2026-10-01 12:00:00";
    }
    return (
      `<item><title>${id < matched ? "fixture" : "other"} dataset ${id}</title>` +
      `<description>Dataset description ${id}</description><size>1048576</size>` +
      `<infohash>${hash}</infohash><link>${site}details/${id}</link></item>`
    );
  });
  return {
    plugin: "academictorrents",
    query: "fixture",
    maxDetails: Math.max(1, matched),
    responses,
    cacheXml: `<rss><channel>${rows.join("")}</channel></rss>`,
  };
}

export function darkWideCase(rows = 2048): ParserCase {
  const fixture = darklibriaCase();
  fixture.responseDelayMs = 0;
  const padding = Array.from({ length: rows }, (_, id) => `<div><b>${id}</b><br>text</div>`).join(
    "",
  );
  const url = "https://darklibria.it/search?page=1&find=fixture";
  const listing = fixture.responses[url];
  fixture.responses[url] = padding + (typeof listing === "string" ? listing : (listing.body ?? ""));
  return fixture;
}

export function unionCase(pages = 5): ParserCase {
  const site = "http://uniondht.org";
  const responses: Record<string, string> = {};
  for (let page = 1; page <= pages; page += 1) {
    const ids = [(page - 1) * 2, (page - 1) * 2 + 1];
    if (page > 1) ids.unshift(0);
    responses[`${site}/tracker.php?nm=fixture&start=${(page - 1) * 50}`] =
      `<p class="floatR">Results: ${pages * 50}</p>` +
      ids
        .map(
          (id) =>
            `<tr id="tor${id}"><td><a href="/topic-${id}"><b>Fixture ${id}</b></a>` +
            `<a href="/dl.php?id=${id}">download</a>1 GB</td><td class="seed">10</td>` +
            '<td class="leech"><b>2</b></td></tr>',
        )
        .join("");
  }
  return { plugin: "uniondht", query: "fixture", maxPages: pages, responses };
}

/** Empty profiles cover import/transport compatibility, never a functional speed claim. */
export async function benchmarkFixtures(plugin: string): Promise<BenchmarkFixture[]> {
  const captures: Partial<Record<string, string[]>> = {
    elitetorrent: ["elitetorrent-inception", "elitetorrent-matrix"],
    bitsearch: ["bitsearch"],
    solidtorrents: ["solidtorrents"],
    ali213: ["ali213-current"],
    pirateiro: ["pirateiro"],
  };
  const names = captures[plugin];
  if (names) {
    return Promise.all(
      names.map(async (name) => {
        const fixture = (await Bun.file(
          resolve(FIXTURES_DIR, "parsers", `${name}.json`),
        ).json()) as ParserCase;
        // Captures are checked separately against their original source hash.
        // Paired comparisons intentionally replay the same bytes through two revisions.
        const paired = { ...fixture };
        delete paired.sourceSha256;
        if (plugin === "ali213") paired.expectEmpty = true;
        return { name, evidence: "capture" as const, ordered: false, case: paired };
      }),
    );
  }
  const synthetic = (name: string, fixture: ParserCase, ordered = false): BenchmarkFixture => ({
    name,
    case: fixture,
    evidence: "synthetic",
    ordered,
  });
  switch (plugin) {
    case "academictorrents": {
      const small = academicCase(50);
      const large = academicCase();
      return [
        synthetic("cache-small", small),
        synthetic("cache-large", large),
        synthetic("cache-malformed", {
          ...small,
          cacheXml: `${small.cacheXml ?? ""}<broken`,
          expectEmpty: true,
        }),
      ];
    }
    case "darklibria":
      return [
        synthetic("two-pages", { ...darklibriaCase(), responseDelayMs: 0 }),
        synthetic("wide-dom", darkWideCase()),
      ];
    case "audiobookbay":
      return [synthetic("eight-pages", { ...audiobookCase(), responseDelayMs: 0 })];
    case "yts":
      return [synthetic("eight-pages", { ...ytsCase(), responseDelayMs: 0 }, true)];
    case "uniondht":
      return [synthetic("five-pages", unionCase(), true)];
    default:
      return [
        {
          name: "empty-profile",
          evidence: "empty",
          ordered: false,
          case: { plugin, query: "fixture", responses: {}, expectEmpty: true, emptyResponse: "" },
        },
      ];
  }
}
