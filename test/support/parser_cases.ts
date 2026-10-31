/**
 * Build deterministic parser fixtures for large and paginated workloads.
 * @file
 */
import { darklibriaCase } from "./concurrent_cases";
import type { ParserCase } from "./parser_replay";

/** Build a large Academic Torrents XML catalog with a controlled number of matches. */
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

/** Expand a dark-libria fixture to stress bounded detail resolution. */
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

/** Build a paginated UnionDHT replay with predictable search results. */
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
