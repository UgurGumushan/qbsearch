# New search engines — 2026-10-03

Nine original standalone engines are included in the 0.1.11 release.
FOSS Torrents is deferred. The collection now contains 58 engines.

These additions are provisional. Deterministic tests exercise the actual
Python engines against synthetic protocol fixtures. They verify links,
metadata, request budgets and concurrency. Fresh browser HTTP captures below
also exercise current remote data through the released Python engines. Seven
engines return valid results; two endpoints return HTTP 403. Production latency
and magnet swarm availability remain unverified.

## Sources and admission decisions

| Candidate        | Decision                 | Implementation and remaining evidence                                                                                                                                                                                                                                                                                                                                       |
| ---------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Knaben           | Implemented, provisional | [API v2 GET contract](https://knaben.org/api/v2/) with one seed-sorted page. Fresh browser captures for `ubuntu` and `debian` confirm the current v2 fields and produce valid actual-engine results. Native client connectivity and swarm availability remain unverified.                                                                                                   |
| TorrentFunk      | Implemented, provisional | [Public JSON search API](https://www.torrentfunk.com/apis.html) supplies names, sizes, swarm counts and magnets without an API key.                                                                                                                                                                                                                                         |
| Internet Archive | Implemented, provisional | [BitTorrent search filter](https://help.archive.org/help/archive-bittorrents/) followed by the [metadata API](https://archive.org/developers/md-read.html). Emits only explicitly listed public item torrents. Payload size and live swarm counts remain unknown.                                                                                                           |
| FOSS Torrents    | Deferred                 | The [project search page](https://fosstorrents.com/search/) exposes a client-side search field; accessible category pages contain popular/recent subsets. A verified source-wide request or complete catalog is still needed. Initial native requests could not fetch the client search assets. This does not establish that the site is permanently impossible to support. |
| LinuxTracker     | Implemented, provisional | Current [public listing](https://linuxtracker.org/torrents/?q=Y) includes hashes in detail URLs. Constructs magnets directly and keeps local tracker counts separate from external observations.                                                                                                                                                                            |
| Torlock          | Implemented, provisional | [Hosted Torznab API](https://www.torlock.com/apis.html) supplies magnets and metadata without sponsored HTML rows. Datacenter traffic can be filtered. No automatic whitelisting request is sent.                                                                                                                                                                           |
| UIndex           | Implemented, provisional | Guest route and table layout from the [maintainer's reference](https://github.com/tolotp/qbittorrent-search-plugins-de-busqueda/blob/main/Plugins/%28deprecated%29%20uindex.py). That engine is marked deprecated; confirm current search and magnet behavior before promotion.                                                                                             |
| AniLiberty       | Implemented, provisional | [Current API v1 schema](https://anilibria.top/storage/api/docs/v1): release search, then release-torrent metadata. Skips blocked releases and avoids the retired AniLibria v3 API.                                                                                                                                                                                          |
| TorrentClaw      | Implemented, provisional | Public response described by the [reference engine](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/src/engines/torrentclaw.py). Constructs magnets from public hashes when anonymous responses omit ready magnets.                                                                                                                                  |
| FileMood         | Implemented, provisional | Title-search route from the [reference engine](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/src/engines/filemood.py). Constructs DHT magnets from listing hashes. No private tracker URLs or passkeys from the reference are copied.                                                                                                              |

The new implementations use repository safety helpers and Python's standard
library. Each file installs independently. Original neutral icons are included.
The new files use GPL-3.0-or-later; legacy engines retain their recorded licenses.

## Measured work and expected wins

There is no previous repository engine for these sources, so a before/after
runtime percentage would be invented. Request counts below are verified by
actual-engine replay. One request means one successful HTTP attempt; retries
can raise attempts to three per URL.

| Engine           | Verified work / hard bound                                                            | Win to expect                                                                                    | Limit                                                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Knaben           | 100 records from one API request; no detail fetches                                   | One response supplies hashes, titles, sizes and swarm counts                                     | Current v2 fields confirmed by fresh captures; native client and swarm availability remain unverified                             |
| TorrentFunk      | 100 records from one request; three repeated searches use one request                 | No detail requests; identical searches within 15 minutes reuse a disk cache                      | Cache is best effort if the engine directory is not writable                                                                      |
| Internet Archive | 20 public items from 21 requests, at most four simultaneous metadata requests         | Overlaps independent metadata reads and avoids fetching binary torrents during search            | A metadata request per item is necessary to verify its public torrent; no request-count reduction beyond deduplication is claimed |
| FOSS Torrents    | No engine shipped                                                                     | No justified win yet                                                                             | Needs a verified complete project search contract                                                                                 |
| LinuxTracker     | Two unique results from one listing request; output cap enforced                      | No detail fetches; memory holds one table row rather than a DOM                                  | One listing page, without exhaustive historical pagination                                                                        |
| Torlock          | Two unique results from one XML request; three repeated searches use one request      | No sponsored-row scraping or detail fetch; identical searches within one minute reuse disk cache | IP filtering may prevent access                                                                                                   |
| UIndex           | Two unique results from one listing request; supplied magnets retained                | No detail requests or whole-page DOM                                                             | Deprecated reference needs a fresh remote capture                                                                                 |
| AniLiberty       | Eight unique releases from nine requests, at most four simultaneous metadata requests | Gets torrent variants once per release and overlaps independent releases                         | Current schema separates search from torrent metadata; no single-request promise                                                  |
| TorrentClaw      | 100 torrent records from one search response                                          | Public hashes avoid magnet-key and per-result requests                                           | At most 50 content groups and 100 emitted torrent variants                                                                        |
| FileMood         | Two unique results from one listing request; full titles and sizes retained           | No detail requests or fixed inter-page sleeps                                                    | One page; DHT availability and swarm counts are unverified                                                                        |

All engines bound results, validate links/hashes, deduplicate, and use the
generated deadline, retry and response-size helpers. Internet Archive
deduplicates item identifiers. Disk caches use hashed URL keys, atomic writes,
eight completed entries per engine and the response-size cap; they exclude
malformed responses and access challenges. Read-only installations still work.

Checks live in [new_plugins.test.ts](../test/new_plugins.test.ts).
Synthetic fixture timings are not presented as service latency.

## Live observations and promotion

```sh
bun run test -- --live --plugin knaben --plugin torrentfunk --plugin torlock \
  --plugin torrentclaw --plugin linuxtracker --plugin uindex --plugin filemood \
  --plugin aniliberty --plugin internetarchive --require-results
```

On 2026-10-03, the native Bun probes exhausted three connection attempts each
and reported “Unable to connect.” That run received no remote HTTP status.
Queries were `ubuntu` for Knaben, TorrentFunk, Torlock, LinuxTracker, UIndex and
Internet Archive; `netbsd` for FileMood; `naruto` for AniLiberty; and
`big buck bunny` for TorrentClaw. The live helper suite also could not bind its
local HTTP test server.

### Fresh browser captures and actual-engine replay

An isolated browser session could reach the services. The existing offline
harness ran the released standalone Python engines against fresh browser
responses. The Knaben `ubuntu` capture used the browser's JSON document text
and navigation status; the remaining captures used bounded browser fetches
with credentials omitted. Source SHA-256 checks
tie every replay to the tested engine. All replayed requests have captured
responses, and every returned row passes the qBittorrent result checks.

| Engine           | Queries                     | Actual-engine result counts | HTTP outcome                                            | Engine requests per query |
| ---------------- | --------------------------- | --------------------------- | ------------------------------------------------------- | ------------------------- |
| Knaben           | `ubuntu`, `debian`          | 88, 16                      | 200                                                     | 1, 1                      |
| TorrentFunk      | `ubuntu`, `linux`, `debian` | 4, 18, 0                    | 200; Debian API explicitly reports zero matches         | 1 each                    |
| Torlock          | `ubuntu`, `debian`          | 100, 100                    | 200                                                     | 1, 1                      |
| LinuxTracker     | `ubuntu`, `debian`          | 25, 25                      | 200                                                     | 1, 1                      |
| FileMood         | `netbsd`, `freebsd`         | 20, 20                      | 200                                                     | 1, 1                      |
| AniLiberty       | `naruto`, `bleach`          | 9, 14                       | 200 for search and release metadata                     | 4, 3                      |
| Internet Archive | `ubuntu`, `debian`          | 18, 20                      | 200 for search and all 20 item metadata reads per query | 21, 21                    |
| UIndex           | `ubuntu`                    | 0                           | 403 Cloudflare challenge                                | 1                         |
| TorrentClaw      | `big buck bunny`            | 0                           | 403 Forbidden                                           | 1                         |

These are 17 search cases, 62 captured responses and 477 validated result
rows. The request counts describe the URLs read by the Python engines from
the saved responses; browser navigation and capture requests are additional.
The two 403 responses establish blocked access, with successful parsing for
those sources still unverified. TorrentFunk's empty Debian result agrees with
its API's `count: 0` and `total_found: 0`.

The Archive Ubuntu query excluded both items whose torrent metadata marked
the file private. Two emitted public torrent links were downloaded through
the browser and passed the existing BEP 3/BEP 52 structural metainfo checks:

- `ubuntu-20.04.3-desktop-amd64_202205_archive.torrent`: 31,347 bytes.
- `kubuntu-6.06-desktop-powerpc_archive.torrent`: 29,765 bytes.

The JSON captures, source hashes, complete replay results and downloaded
metainfo are saved under ignored `working/live-browser-20261003/`; `report.json`
indexes the evidence and `finalize_evidence.py` reruns every saved case. This
verification checks current response compatibility. Native Bun networking
and BitTorrent swarm/payload downloads remain unverified. Catalog statuses
remain `intermittent`; their notes now include the actual remote outcomes.
