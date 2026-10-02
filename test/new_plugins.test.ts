import { expect, test } from "bun:test";
import { buildProbeUrl } from "./live/plugin_source";
import { countResultMarkers } from "./live/http";
import { PLUGIN_SOURCES } from "./plugin_sources";
import {
  assertUsableParserResults,
  replayParserFixture as replay,
  type ParserCase,
} from "./support/parser_replay";

const hash = (id: number): string => id.toString(16).padStart(40, "0");
const magnet = (id: number): string => `magnet:?xt=urn:btih:${hash(id)}&dn=fixture`;
const query = "ubuntu";
const apiUrls = {
  knaben: "https://api.knaben.org/v2/search?q=ubuntu&s=100&f=0&o=seeders&d=desc",
  torrentfunk:
    "https://www.torrentfunk.com/api/search.json?q=ubuntu&category=0&sort=seeds&order=desc&limit=100&page=1",
  torrentclaw: "https://torrentclaw.com/api/v1/search?q=ubuntu&limit=50",
  torlock: "https://www.torlock.com/torznab/api?t=search&q=ubuntu&limit=100&offset=0",
} as const;

function jsonReply(plugin: "knaben" | "torrentfunk" | "torrentclaw", ids: number[]): string {
  const rows = ids.map((id) => ({
    title: `Ubuntu ${id}`,
    name: `Ubuntu ${id}`,
    rawTitle: `Ubuntu ${id}`,
    magnet: magnet(id),
    magnetUrl: magnet(id),
    infohash: hash(id).toUpperCase(),
    infoHash: hash(id),
    hash: hash(id),
    bytes: 1024,
    size_bytes: 1024,
    sizeBytes: 1024,
    seeders: 12,
    seeds: 12,
    peers: 2,
    leechers: 2,
    date: "2026-10-01T12:00:00Z",
    added_iso: "2026-10-01T12:00:00Z",
    uploadedAtISO: "2026-10-01T12:00:00Z",
    url: `https://example.com/${id}`,
    details: `https://example.com/${id}`,
  }));
  if (plugin === "knaben") return JSON.stringify({ hits: rows });
  if (plugin === "torrentfunk") return JSON.stringify({ status: "ok", results: rows });
  return JSON.stringify({
    results: [{ title: "Ubuntu", contentUrl: "https://torrentclaw.com/c/ubuntu", torrents: rows }],
  });
}

for (const plugin of ["knaben", "torrentfunk", "torrentclaw"] as const) {
  test(`${plugin} retains metadata, deduplicates hashes and needs one request for 100 results`, async () => {
    const ids = Array.from({ length: 100 }, (_, id) => id + 1);
    const report = await replay(
      {
        plugin,
        query,
        maxDetails: 100,
        responses: { [apiUrls[plugin]]: jsonReply(plugin, ids) },
      },
      { measure: true },
    );
    assertUsableParserResults(report, true);
    expect(report.records).toHaveLength(100);
    expect(report.requests).toEqual([apiUrls[plugin]]);
    expect(report.records[0]).toMatchObject({
      name: "Ubuntu 1",
      link: magnet(1),
      size: 1024,
      seeds: 12,
      leech: 2,
    });
    expect(report.records[0].pub_date).toBe(1790856000);
    expect(report.metrics?.usableResults).toBe(100);
    const duplicate = await replay({
      plugin,
      query,
      responses: { [apiUrls[plugin]]: jsonReply(plugin, [1, 1, 2]) },
    });
    assertUsableParserResults(duplicate, true);
    expect(duplicate.records.map((row) => row.name)).toEqual(["Ubuntu 1", "Ubuntu 2"]);
  });

  test(`${plugin} tolerates invalid JSON, access failures, empty queries and unsupported categories`, async () => {
    for (const response of [
      "<html>challenge</html>",
      "null",
      "[]",
      { status: 403, body: "blocked" },
    ]) {
      const report = await replay({ plugin, query, responses: { [apiUrls[plugin]]: response } });
      expect(report.code).toBe(0);
      expect(report.errors).toEqual([]);
      expect(report.records).toEqual([]);
      expect(report.requests).toHaveLength(1);
    }
    for (const overrides of [{ query: "" }, { category: "unsupported" }]) {
      const report = await replay({ plugin, query, responses: {}, ...overrides });
      expect(report.errors).toEqual([]);
      expect(report.requests).toEqual([]);
    }
  });
}

test("TorrentClaw uses public hashes when anonymous responses omit magnets", async () => {
  const body = JSON.stringify({
    results: [
      {
        title: "Ubuntu",
        torrents: [
          { rawTitle: "Ubuntu x86_64", infoHash: hash(1) },
          { rawTitle: "invalid", infoHash: "bad", magnetUrl: "magnet:?dn=bad" },
          { rawTitle: "", infoHash: hash(2), magnetUrl: "https://example.com/ad" },
          {
            rawTitle: "Ubuntu second",
            infoHash: hash(3),
            seeders: true,
            leechers: -4,
            sizeBytes: true,
          },
        ],
      },
    ],
  });
  const report = await replay({
    plugin: "torrentclaw",
    query,
    responses: { [apiUrls.torrentclaw]: body },
  });
  assertUsableParserResults(report, true);
  expect(report.records).toHaveLength(3);
  expect(report.records[0].link).toBe(`magnet:?xt=urn:btih:${hash(1)}&dn=Ubuntu%20x86_64`);
  expect(report.records[2]).toMatchObject({ seeds: -1, leech: -1, size: -1 });
});

function torznab(ids: number[]): string {
  return `<rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel>${ids
    .map(
      (id) =>
        `<item><title>Ubuntu &amp; ${id}</title><comments>https://www.torlock.com/torrent/${id}/ubuntu.html</comments>
    <pubDate>Thu, 01 Oct 2026 12:00:00 GMT</pubDate>
    <enclosure url="${magnet(id).replaceAll("&", "&amp;")}" length="2048"/>
    <torznab:attr name="infohash" value="${hash(id)}"/>
    <torznab:attr name="seeders" value="12"/><torznab:attr name="peers" value="14"/></item>`,
    )
    .join("")}</channel></rss>`;
}

test("Torlock reads namespace attributes, enclosure magnets and total peer counts", async () => {
  const report = await replay({
    plugin: "torlock",
    query,
    responses: { [apiUrls.torlock]: torznab([1, 1, 2]) },
  });
  assertUsableParserResults(report, true);
  expect(report.records).toHaveLength(2);
  expect(report.requests).toHaveLength(1);
  expect(report.records[0]).toMatchObject({
    name: "Ubuntu & 1",
    link: magnet(1),
    seeds: 12,
    leech: 2,
    size: 2048,
    pub_date: 1790856000,
  });
});

test("Torlock rejects malformed XML and entity declarations without emitting rows", async () => {
  for (const body of [
    "<rss>",
    `<!DOCTYPE rss [<!ENTITY x "test">]>${torznab([1])}`,
    "<error code='403'/>",
  ]) {
    const report = await replay({
      plugin: "torlock",
      query,
      responses: { [apiUrls.torlock]: body },
    });
    expect(report.errors).toEqual([]);
    expect(report.records).toEqual([]);
    expect(report.requests).toHaveLength(1);
  }
});

for (const plugin of ["torrentfunk", "torlock"] as const) {
  test(`${plugin} reuses the cached exact query across successive engine instances`, async () => {
    const report = await replay({
      plugin,
      query,
      repeatSearches: 3,
      responses: {
        [apiUrls[plugin]]: plugin === "torlock" ? torznab([1]) : jsonReply(plugin, [1]),
      },
    });
    assertUsableParserResults(report, true);
    expect(report.records).toHaveLength(3);
    expect(report.requests).toEqual([apiUrls[plugin]]);
    expect(report.records[0]).toEqual(report.records[2]);
  });
}

const htmlUrls = {
  linuxtracker: "https://linuxtracker.org/torrents/?q=ubuntu",
  uindex: "https://uindex.org/search.php?search=ubuntu&c=0",
  filemood: "https://filemood.com/result?q=ubuntu%20in%3Atitle&f=0",
} as const;
function htmlRow(plugin: keyof typeof htmlUrls, id: number): string {
  if (plugin === "linuxtracker") {
    return `<tr><td><a href='/torrents/${hash(id)}/'>Ubuntu &amp; ${id}.iso</a><span>Ubuntu · 2 GB</span></td><td>Ubuntu</td><td>Oct 1, 2026</td><td>3.4 GB</td><td>12 +130 ext</td><td>2 +4 ext</td></tr>`;
  }
  if (plugin === "uindex") {
    return `<tr><td>Software</td><td><a href='/details.php?id=${id}'>Ubuntu &amp; ${id}.iso</a><a href='${magnet(id).replaceAll("&", "&amp;")}'>Magnet</a></td><td>3.4 GB</td><td>today</td><td><span class='sr-seed'>12</span></td><td>2</td></tr>`;
  }
  return `<tr><td><a title='Ubuntu &amp; ${id}.iso' href='/ubuntu-${hash(id)}.html'>truncated…</a></td><td>3.4 GB</td></tr>`;
}

for (const plugin of ["linuxtracker", "uindex", "filemood"] as const) {
  test(`${plugin} emits listing downloads, full titles and sizes with no detail requests`, async () => {
    const body = `<table>${htmlRow(plugin, 1)}${htmlRow(plugin, 1)}${htmlRow(plugin, 2)}</table>`;
    const report = await replay({ plugin, query, responses: { [htmlUrls[plugin]]: body } });
    assertUsableParserResults(report, true);
    expect(report.records).toHaveLength(2);
    expect(report.records[0]).toMatchObject({ name: "Ubuntu & 1.iso", size: "3.4 GB" });
    if (plugin !== "filemood") expect(report.records[0]).toMatchObject({ seeds: 12, leech: 2 });
    expect(report.requests).toEqual([htmlUrls[plugin]]);
    expect(report.records.map((row) => row.link)).toEqual(
      plugin === "uindex"
        ? [magnet(1), magnet(2)]
        : [1, 2].map((id) => `magnet:?xt=urn:btih:${hash(id)}&dn=Ubuntu%20%26%20${id}.iso`),
    );
  });

  test(`${plugin} enforces the output cap and ignores unrelated navigation and hosts`, async () => {
    const body = `<table><tr><td><a href='https://[broken'>malformed</a><a href='https://ads.example/ubuntu-${hash(99)}.html'>sponsored</a></td></tr>${Array.from({ length: 100 }, (_, id) => htmlRow(plugin, id + 1)).join("")}</table>`;
    const report = await replay({
      plugin,
      query,
      maxDetails: 3,
      responses: { [htmlUrls[plugin]]: body },
    });
    assertUsableParserResults(report, true);
    expect(report.records).toHaveLength(3);
    expect(report.requests).toHaveLength(1);
    expect(report.records.some((row) => row.name === "sponsored")).toBeFalse();
  });
}

const libertySearch =
  "https://aniliberty.top/api/v1/app/search/releases?query=naruto&include=id,alias,name,is_blocked_by_geo,is_blocked_by_copyrights";
const libertyTorrents = (id: number): string =>
  `https://aniliberty.top/api/v1/anime/torrents/release/${id}?include=hash,size,label,magnet,seeders,leechers,created_at`;

test("AniLiberty uses at most eight unique public releases and four concurrent metadata requests", async () => {
  const releases = Array.from({ length: 12 }, (_, id) => ({
    id: id + 1,
    alias: `naruto-${id + 1}`,
    name: { main: "Наруто" },
  }));
  const responses: ParserCase["responses"] = {
    [libertySearch]: JSON.stringify([
      { id: 99, is_blocked_by_geo: true },
      releases[0],
      ...releases,
    ]),
  };
  for (const release of releases.slice(0, 8))
    responses[libertyTorrents(release.id)] = JSON.stringify([
      {
        label: `Наруто ${release.id}`,
        hash: hash(release.id),
        size: 2048,
        seeders: 12,
        leechers: 2,
        created_at: "2026-10-01T12:00:00Z",
      },
    ]);
  const report = await replay({
    plugin: "aniliberty",
    query: "naruto",
    maxDetails: 100,
    maxWorkers: 16,
    responseDelayMs: 20,
    responses,
  });
  assertUsableParserResults(report, true);
  expect(report.records).toHaveLength(8);
  expect(report.requests).toHaveLength(9);
  expect(report.peakConcurrentRequests).toBe(4);
  expect(report.records[0]).toMatchObject({ size: 2048, seeds: 12, leech: 2 });
  expect(new Set(report.records.map((row) => row.name)).size).toBe(8);
});

const archiveUrl = (text: string): string => {
  const params = new URLSearchParams();
  params.set("q", `(${text}) AND format:"Archive BitTorrent" AND -mediatype:collection`);
  params.append("fl[]", "identifier");
  params.append("fl[]", "title");
  params.set("rows", "20");
  params.set("page", "1");
  params.set("output", "json");
  return `https://archive.org/advancedsearch.php?${params.toString().replaceAll("%7E", "~")}`;
};

test("Internet Archive only emits public item torrents, with honest payload and swarm metadata", async () => {
  const responses: ParserCase["responses"] = {
    [archiveUrl("ubuntu")]: JSON.stringify({
      response: {
        docs: [
          { identifier: "ubuntu-iso", title: "Ubuntu ISO" },
          { identifier: "ubuntu-iso", title: "duplicate" },
          { identifier: "../invalid", title: "bad" },
          { identifier: "private", title: "Private" },
          { identifier: "restricted", title: "Restricted" },
          { identifier: "missing", title: "Missing" },
        ],
      },
    }),
    "https://archive.org/metadata/ubuntu-iso": JSON.stringify({
      metadata: { publicdate: "2026-10-01T12:00:00Z" },
      files: [
        { name: "unrelated.torrent", format: "Archive BitTorrent", size: "999" },
        { name: "ubuntu-iso_archive.torrent", format: "Archive BitTorrent", size: "777" },
      ],
    }),
    "https://archive.org/metadata/private": JSON.stringify({
      files: [{ name: "private_archive.torrent", format: "Archive BitTorrent", private: "true" }],
    }),
    "https://archive.org/metadata/restricted": JSON.stringify({
      metadata: { "access-restricted-item": "true" },
      files: [{ name: "restricted_archive.torrent", format: "Archive BitTorrent" }],
    }),
    "https://archive.org/metadata/missing": "{}",
  };
  const report = await replay({
    plugin: "internetarchive",
    query,
    maxDetails: 100,
    maxWorkers: 16,
    responseDelayMs: 20,
    responses,
  });
  assertUsableParserResults(report, true);
  expect(report.records).toEqual([
    {
      name: "Ubuntu ISO",
      link: "https://archive.org/download/ubuntu-iso/ubuntu-iso_archive.torrent",
      desc_link: "https://archive.org/details/ubuntu-iso",
      engine_url: "https://archive.org",
      size: -1,
      seeds: -1,
      leech: -1,
      pub_date: 1790856000,
    },
  ]);
  expect(report.requests).toHaveLength(5);
  expect(report.peakConcurrentRequests).toBe(4);
});

test("new live probes target actual search requests and structured result markers", () => {
  expect(
    buildProbeUrl(PLUGIN_SOURCES.torrentfunk, "https://www.torrentfunk.com", query, "all"),
  ).toBe(apiUrls.torrentfunk);
  expect(buildProbeUrl(PLUGIN_SOURCES.uindex, "https://uindex.org", query, "all")).toBe(
    htmlUrls.uindex,
  );
  expect(buildProbeUrl(PLUGIN_SOURCES.filemood, "https://filemood.com", query, "all")).toBe(
    htmlUrls.filemood,
  );
  expect(buildProbeUrl(PLUGIN_SOURCES.internetarchive, "https://archive.org", query, "all")).toBe(
    archiveUrl(query),
  );
  expect(countResultMarkers(jsonReply("knaben", [1, 2]), "application/json")).toBe(2);
  expect(countResultMarkers(torznab([1, 2]), "application/xml")).toBe(2);
});

test("new search URLs encode ampersands, plus signs, slashes and Unicode once", async () => {
  const text = "Ubuntu & Linux/+日本";
  const encoded = encodeURIComponent(text);
  const fixtures: {
    plugin: keyof typeof PLUGIN_SOURCES;
    site: string;
    url: string;
    body: string;
  }[] = [
    {
      plugin: "knaben",
      site: "https://knaben.org",
      url: apiUrls.knaben.replace("ubuntu", encoded),
      body: jsonReply("knaben", [1]),
    },
    {
      plugin: "torrentfunk",
      site: "https://www.torrentfunk.com",
      url: apiUrls.torrentfunk.replace("ubuntu", encoded),
      body: jsonReply("torrentfunk", [1]),
    },
    {
      plugin: "torrentclaw",
      site: "https://torrentclaw.com",
      url: apiUrls.torrentclaw.replace("ubuntu", encoded),
      body: jsonReply("torrentclaw", [1]),
    },
    {
      plugin: "torlock",
      site: "https://www.torlock.com",
      url: apiUrls.torlock.replace("ubuntu", encoded),
      body: torznab([1]),
    },
    {
      plugin: "uindex",
      site: "https://uindex.org",
      url: htmlUrls.uindex.replace("ubuntu", encoded),
      body: htmlRow("uindex", 1),
    },
    {
      plugin: "linuxtracker",
      site: "https://linuxtracker.org",
      url: htmlUrls.linuxtracker.replace("ubuntu", encoded),
      body: htmlRow("linuxtracker", 1),
    },
    {
      plugin: "filemood",
      site: "https://filemood.com",
      url: htmlUrls.filemood.replace("ubuntu", encoded),
      body: htmlRow("filemood", 1),
    },
  ];
  for (const fixture of fixtures) {
    const report = await replay({
      plugin: fixture.plugin,
      query: encoded,
      responses: { [fixture.url]: fixture.body },
    });
    assertUsableParserResults(report, true);
    expect(report.requests).toEqual([fixture.url]);
    expect(buildProbeUrl(PLUGIN_SOURCES[fixture.plugin], fixture.site, text, "all")).toBe(
      fixture.url,
    );
  }
}, 20_000);

test("Internet Archive caps the metadata fan-out at twenty even when the API over-returns", async () => {
  const items = Array.from({ length: 100 }, (_, id) => ({
    identifier: `ubuntu-${id}`,
    title: `Ubuntu ${id}`,
  }));
  const responses: ParserCase["responses"] = {
    [archiveUrl("ubuntu")]: JSON.stringify({ response: { docs: items } }),
  };
  for (const item of items.slice(0, 20))
    responses[`https://archive.org/metadata/${item.identifier}`] = JSON.stringify({
      files: [{ name: `${item.identifier}_archive.torrent`, format: "Archive BitTorrent" }],
    });
  const report = await replay(
    {
      plugin: "internetarchive",
      query,
      maxDetails: 100,
      maxWorkers: 16,
      responseDelayMs: 20,
      responses,
    },
    { measure: true },
  );
  assertUsableParserResults(report, true);
  expect(report.requests).toHaveLength(21);
  expect(report.records).toHaveLength(20);
  expect(report.peakConcurrentRequests).toBe(4);
  expect(report.metrics?.usableResults).toBe(20);
});

test("new transport rejects oversized responses before parsing or printing", async () => {
  const report = await replay({
    plugin: "knaben",
    query,
    responses: { [apiUrls.knaben]: " ".repeat(4 * 1024 * 1024 + 1) + jsonReply("knaben", [1]) },
  });
  expect(report.errors).toEqual([]);
  expect(report.records).toEqual([]);
  expect(report.requests).toHaveLength(1);
});
