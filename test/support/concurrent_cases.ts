import type { ParserCase } from "./parser_replay";

/** Small generated pages exercise real parsers without storing redundant HTML. */
export function audiobookCase(pages = 8, maxDetails = 32): ParserCase {
  const site = "https://audiobookbay.org/";
  const responses: Record<string, string> = { [site]: "Available" };
  for (let page = 1; page <= pages; page += 1) {
    const start = (page - 1) * 4;
    const ids = [start, start + 1, start + 2, start + 3];
    if (page > 1) ids.unshift(0);
    responses[`${site}/page/${page}/?s=fixture&cat=all`] =
      ids
        .map(
          (id) =>
            `<div class="post"><h2 class="postTitle"><a href="book/${id}">Book ${id}</a></h2></div>`,
        )
        .join("") + `<a title="»»" href="/page/${pages}/">Last</a>`;
    for (const id of ids) {
      responses[`${site}book/${id}`] =
        `<span>Info Hash:</span><span>${(id + 1).toString(16).padStart(40, "0")}</span>` +
        "<span>Combined File Size:</span><span>1 GB</span>";
    }
  }
  return {
    plugin: "audiobookbay",
    query: "fixture",
    maxPages: pages,
    maxDetails,
    responses,
    responseDelayMs: 20,
  };
}

export const YTS_SEARCH_URL =
  "https://movies-api.accel.li/api/v2/list_movies.json?query_term=fixture";

export function ytsPage(page: number, totalPages: number): string {
  return JSON.stringify({
    status: "ok",
    status_message: "OK",
    data: {
      movie_count: totalPages * 2,
      limit: 2,
      page_number: page,
      movies: [page === 1 ? 1 : page * 2 - 1, page * 2, 1].map((id) => ({
        id,
        url: `https://yts.bz/movies/fixture-${id}`,
        title: `Fixture ${id}`,
        torrents: [
          {
            url: `https://example.test/${id}.torrent`,
            seeds: 10,
            peers: 2,
            size_bytes: 100,
            size: "100 B",
            quality: "1080p",
            type: "bluray",
            video_codec: "x264",
          },
        ],
      })),
    },
  });
}

export function ytsCase(pages = 8): ParserCase {
  const responses: Record<string, string> = { [YTS_SEARCH_URL]: ytsPage(1, pages) };
  for (let page = 2; page <= pages; page += 1) {
    responses[`${YTS_SEARCH_URL}&page=${page}`] = ytsPage(page, pages);
  }
  return { plugin: "yts", query: "fixture", maxPages: pages, responses, responseDelayMs: 20 };
}

/** Two pages expose the case where serial nested jobs would waste most workers. */
export function darklibriaCase(): ParserCase {
  const site = "https://darklibria.it/";
  const responses: Record<string, string> = {};
  for (let page = 1; page <= 2; page += 1) {
    const ids = Array.from({ length: 16 }, (_, index) => (page - 1) * 16 + index);
    responses[`${site}search?page=${page}&find=fixture`] =
      '<span class="text text-light mt-0">Showing anime 1-16 of 32</span>' +
      ids
        .map(
          (id) =>
            `<tbody style="vertical-align: center"><tr><td><a href="${site}series/${id}">Anime ${id}</a></td></tr></tbody>`,
        )
        .join("");
    for (const id of ids) {
      const hash = (id + 1).toString(16).padStart(40, "0");
      responses[`${site}series/${id}`] =
        `<span id="russian_name">Anime ${id}</span><table><tr class="torrent">` +
        "<td>TV</td><td>1080p</td><td>1 Гб</td><td>2026-10-01 12:00:00</td>" +
        `<td><a title="Magnet-ссылка" href="magnet:?xt=urn:btih:${hash}">Download</a></td>` +
        "<td>10</td><td>2</td></tr></table>";
    }
  }
  return {
    plugin: "darklibria",
    query: "fixture",
    maxPages: 2,
    maxDetails: 16,
    responses,
    responseDelayMs: 20,
  };
}
