# Search performance

The nine new engines and their measured request budgets are documented in
[NEW_PLUGINS.md](NEW_PLUGINS.md). They have no previous repository implementations;
the report therefore makes no before/after latency percentage claims.

## Optimization decisions for the v0.1.10 baseline

New comparisons use release `v0.1.10`, commit
`2877d82cc4399791e24bbe28611648ac911a96da`. The worker-limit and parallel-helper
improvements reported later on this page were already shipped in that release
and are not credited again.

The implemented optimizations change three engines:

- Elitetorrent uses the initial search HTML as page one. Both minimized public
  captures contain identical root/page-one bodies. This removes one request:
  three to two for `inception`, and four to three for `matrix`.
- Darklibria appends DOM content to a list and scans its parser path by index,
  deleting completed suffixes in place. Its public `content` property still
  returns a tuple snapshot. This removes repeated copies on wide HTML trees.
- UnionDHT emits each completed page in order and clears that page's result
  dictionaries. Its cross-page deduplication set remains in place. Partial
  rows completed before a parser exception still reach the final flush.

The complete inventory comparison covers 49 source pairs and 53 fixtures on
Python 3.9.6, with two warmup pairs and 20 measured pairs per timing/allocation
mode. Twelve fixtures emit positive results with matching record dictionaries;
the other 41 are explicitly unverified empty/malformed cases. Rutor's empty
profile emits an unusable diagnostic containing its temporary source path, so
those diagnostic dictionaries differ between profiles; neither counts as a
usable result. The inventory artifact is
`working/performance/benchmark-2026-10-01T21-49-21-840Z/report.json`.

| Controlled workload                                                                      | Baseline median | Optimized median | Outcome                                                |
| ---------------------------------------------------------------------------------------- | --------------: | ---------------: | ------------------------------------------------------ |
| Darklibria wide DOM, 2,048 padding rows, 32 valid records, zero delay, four workers: CPU |        175.9 ms |          62.8 ms | 64.3% less CPU, 2.80× faster                           |
| Darklibria same workload: total                                                          |        175.5 ms |          62.4 ms | 64.5% less elapsed time                                |
| Elitetorrent `inception`: logical HTTP fetches                                           |               3 |                2 | One fewer fetch, 33.3%                                 |
| Elitetorrent `matrix`: logical HTTP fetches                                              |               4 |                3 | One fewer fetch, 25%                                   |
| Elitetorrent `inception`, one worker, 100 ms responses: total                            |        322.0 ms |         218.7 ms | 32.1% less elapsed time                                |
| UnionDHT five pages: requests completed before first output                              |               5 |                1 | Emits the first page before the remaining four fetches |
| UnionDHT five pages, one worker, 100 ms responses: first valid result                    |        520.9 ms |         109.7 ms | 78.9% earlier output; total time essentially unchanged |

Darklibria's small two-page fixture shows no material gain. The wide-DOM
representation adds about 0.12 MiB (4.5%) to traced peak allocations in the
inventory run; the benefit is CPU rather than a memory reduction.

The full Python 3.9 scheduling matrix covers 60 comparisons: five positive
fixtures across workers 1/4/16 and four delay profiles. Every comparison
preserves the complete result dictionaries and reports no transport errors.
It records 43 wins, 14 cases without a material gain, and three p95 regression
flags in zero-delay controls. The report is
`working/performance/benchmark-2026-10-01T22-01-41-143Z/report.json`.

The flags are retained rather than removed from the evidence. Focused repeats
of those three controls use 100 fresh timing pairs and 100 separate allocation
pairs, with the same two warmup pairs. None reproduces a regression beyond
the agreed median/p95 limits:

| Zero-delay control                  | Total median before → after | Total p95 before → after |
| ----------------------------------- | --------------------------: | -----------------------: |
| Elitetorrent `matrix`, four workers |          10.354 → 10.388 ms |       10.915 → 10.994 ms |
| Elitetorrent `matrix`, 16 workers   |          10.441 → 10.479 ms |       11.601 → 11.316 ms |
| UnionDHT five pages, one worker     |            5.354 → 5.363 ms |         5.780 → 6.050 ms |

The repeats are saved in `working/performance/cpu-recheck-20261002/`. The
initial inventory's Elitetorrent `inception` p95 flag (12.9 to 17.2 ms with a
9.9 ms median) also does not recur in any of its 12 matrix scenarios. These
repeats support retaining the three changes; they do not erase the original
tail measurements or promise equivalent live-site latency.

A Python 3.11.15 repeat with 20 timing/allocation pairs covers the same five
positive fixtures at four workers with zero delay. All preserve records,
report no errors, and pass the regression limits. Darklibria's wide-DOM total
median falls from 140.5 to 47.5 ms (66.2%); the two Elitetorrent captures retain
their one-request saving. The small Darklibria and zero-delay UnionDHT controls
have no material gain. Its report is
`working/performance/benchmark-2026-10-01T22-55-20-048Z/report.json`.

AcademicTorrents' streaming XML candidate was **rejected**. Twenty paired fresh
Python 3.9 processes on a 10,000-item cache reduced median traced peak
allocations from 10,010,375 to 555,572 bytes (94.5%), but increased median elapsed
time from 27.7 to 41.9 ms (51.3%). The small cache also exceeded the 5% median
regression limit. The existing parser, daily cache format, and metadata request
behavior remain in place. The rejected source and measurements are saved under
`working/performance/benchmark-2026-10-01T21-46-33-730Z/`.

## Reproduce the measurements

```sh
bun run test -- --benchmark
bun run test -- --benchmark --plugin elitetorrent --baseline v0.1.10 --matrix
QBSEARCH_PYTHON=/usr/bin/python3 bun run test -- --benchmark --plugin darklibria
QBSEARCH_PYTHON=/path/to/python3.11 bun run test -- --benchmark --plugin uniondht --matrix
```

The benchmark is a mode of the existing `test` command. It rejects `--live` and
`--watch` combinations. `--plugin` can be repeated; `--baseline` accepts a Git
commit or tag and defaults to `v0.1.10`. Git supplies baseline source bytes into
a temporary directory without changing the checkout. `--samples` defaults to
20 measured pairs and `--warmups` to two pairs. Fewer than 20 samples are marked
exploratory. `--matrix` runs workers 1, 4, and 16 with zero, 20 ms, 100 ms, and
uneven 5/150 ms response delays. The default inventory run uses four workers
and zero delay.

Each pair alternates baseline/candidate order in fresh Python processes.
Allocation tracing runs separately from elapsed/CPU timing. The JSON report
includes median and nearest-rank p95 import time, process startup plus replay,
time to first usable result (null for empty output), total engine time, CPU,
traced peak allocations, process peak RSS, request counts, bytes consumed,
result counts, and peak overlapping requests. Import time measures incremental
plugin loading after the replay framework has loaded its own standard-library
dependencies; process time includes that framework's startup and the replay.
Neither metric is a direct measurement of qBittorrent's application startup.
RSS includes the harness and
loaded fixture; traced allocations start at engine import. Cache fixture setup
is excluded from engine elapsed/CPU time. All reported memory numbers compare
the same harness and fixture on both sides.

Reports, exact fixtures, and both source snapshots are written beneath the
ignored `working/performance/benchmark-<UTC timestamp>/` directory. Source and
fixture SHA-256 hashes and interpreter details are recorded. Result dictionary
multisets must match; engines with ordered output also compare result order.
The comparison covers names, links, sizes, peers, dates, and download targets.
Offline HTTP torrent rows establish output equality, not a live metainfo download.

The replay transport matches GET/POST method, URL, and request body. It supports
direct `urlopen`, custom openers, redirects, response headers/status, and binary
payloads. It blocks real sockets and downloads and isolates plugin files, home
directories, cache writes, cookies, and logging in disposable profiles. An
unexpected request fails a strict fixture. Generic empty profiles explicitly
opt into an empty fallback and are always **unverified** for performance wins.
Those profiles exercise import/transport compatibility across all 49 engines;
they do not establish a healthy search baseline for every engine.

A retained optimization must remove an avoidable request, improve total time
by at least 10%, improve first-result time by at least 25%, save at least 20%
and 5 ms of CPU, or save at least 25% and 1 MiB of traced allocations. A healthy
representative median regression over 5% or p95 regression over 10% rejects
the candidate. Structural regression tests check records, ordering, deduplication,
caps, request overlap, transport isolation, and malformed-cache behavior without
flaky elapsed-time thresholds.

## Outcome for every plugin

"No material candidate" means the code review did not establish an additional
change worth shipping against v0.1.10. It does not mean optimization is
impossible. "Deferred" means the proposed change requires functional evidence
that is currently missing; its possible saving is not an achieved win.

Two subsequent correctness repairs are separate from the optimization timings.
DMHY now retains anchor attributes, emits the supplied magnet, handles entities
and missing dates, and stops at the global result budget. Maxitorrent now
requests consecutive POST pages, reads row sizes before detail resolution,
decodes response bytes, preserves external download hosts, and bounds redirect
cycles. Positive deterministic fixtures cover both repairs. Their current
live parser/download behavior still requires remote evidence; no additional
latency saving is claimed for either engine. The 49-plugin inventory above
records the earlier optimization batch before these repairs.

| Plugin           | Decision              | Additional gain and evidence                                                                                                                            |
| ---------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| academictorrents | Rejected              | 94.5% lower traced peak allocations cost 51.3% more elapsed time; no shipped gain.                                                                      |
| acgrip           | No material candidate | Sequential pagination stops on empty output; no justified new gain.                                                                                     |
| ali213           | Deferred              | Current captured buttons produce no downloadable rows; repair/verify downloads first.                                                                   |
| animetosho       | No material candidate | One JSON response; no avoidable round trip established.                                                                                                 |
| apachetorrent    | No material candidate | Detail work already uses the bounded parallel helper.                                                                                                   |
| audiobookbay     | Deferred              | Page/detail pipeline needs a fresh usable baseline; last functional capture timed out. Prior parallelism is already in v0.1.10.                         |
| bitsearch        | No material candidate | Shared-backend rate limits constrain changes; existing parser/caps retained.                                                                            |
| bt4gprx          | No material candidate | Global result ranking constrains early output; parallel fetching already shipped.                                                                       |
| btdig            | No material candidate | Independent pages already run concurrently.                                                                                                             |
| cpasbien         | No material candidate | Global ranking and unknown pagination constrain a safe scheduling change.                                                                               |
| darklibria       | Implemented           | 64.3% less CPU on the wide-DOM fixture; small-page control has no material gain. Live query still unverified.                                           |
| divxtotal        | Deferred              | Last endpoint evidence was HTTP 522; no usable baseline for a pipeline rewrite.                                                                         |
| dmhy             | Correctness repaired  | Link attributes and supplied magnets retained; metadata, deduplication, and global result cap verified offline. No latency claim.                       |
| dodi_repacks     | No material candidate | Single feed; a material CPU saving was not established.                                                                                                 |
| dontorrent       | Deferred              | Last endpoint evidence was HTTP 522; no usable baseline.                                                                                                |
| elitetorrent     | Implemented           | One fewer HTTP request: 33.3% for the one-row capture, 25% for the two-row capture; result dictionaries preserved.                                      |
| esmeraldatorrent | Deferred              | Last endpoint evidence was HTTP 522; no usable baseline.                                                                                                |
| eztvx            | Deferred              | Known-page parallelism requires a usable functional baseline before claiming a gain.                                                                    |
| fitgirl_repacks  | No material candidate | Single feed; a material CPU saving was not established.                                                                                                 |
| maxitorrent      | Correctness repaired  | Consecutive POST pages, row-size ordering, redirects, external hosts, and cycle bounds verified offline. No latency claim.                              |
| mikan            | No material candidate | One RSS response; no justified new gain.                                                                                                                |
| mikanani         | No material candidate | One listing response; no justified new gain.                                                                                                            |
| mypornclub       | Deferred              | Parallel primary details must preserve ordered web-seed/budget claims; fresh usable capture unavailable. No measured gain claimed.                      |
| naranjatorrent   | Deferred              | Last endpoint evidence was HTTP 522; no usable baseline.                                                                                                |
| nekobt           | No material candidate | One JSON response; no justified new gain.                                                                                                               |
| nyaa_phuong      | No material candidate | Possible text-processing microchanges have no established material benefit.                                                                             |
| nyaapantsu       | No material candidate | Small capped page sequence; no justified new scheduling gain.                                                                                           |
| nyaasi           | No material candidate | Small capped page sequence; no justified new scheduling gain.                                                                                           |
| onlinefix        | No material candidate | Single feed; a material CPU saving was not established.                                                                                                 |
| pirateiro        | Deferred              | Listing replay works; live HTTP torrent downloads need verification before further changes.                                                             |
| rutor            | No material candidate | Page work already uses bounded parallelism.                                                                                                             |
| sktorrent        | No material candidate | Regex/date work is already reused; no measured additional gain.                                                                                         |
| smallgames       | No material candidate | Single-response parsing with a reused regex; no justified new gain.                                                                                     |
| snowfl           | No material candidate | Three dependent token/search steps; no safe token-cache contract established.                                                                           |
| solidtorrents    | No material candidate | Shared-backend rate limits constrain changes; existing parser/caps retained.                                                                            |
| subsplease       | Deferred              | Removing the six-page loop requires proof that the API ignores pagination; no assumption-based request reduction shipped.                               |
| sukebeisi        | No material candidate | Small capped page sequence; no justified new scheduling gain.                                                                                           |
| thepiratebay     | No material candidate | One JSON response; no justified new gain.                                                                                                               |
| therarbg         | No material candidate | Dependent next links constrain parallel pagination.                                                                                                     |
| tokyotoshokan    | Deferred              | Reusing the last continuation body needs a usable baseline; last endpoint evidence was HTTP 403.                                                        |
| tomadivx         | Deferred              | Last endpoint evidence was HTTP 522; no usable baseline.                                                                                                |
| torrent9         | No material candidate | Global ranking and unknown pagination constrain a safe scheduling change.                                                                               |
| torrentdownload  | No material candidate | Unknown-pagination stopping must remain sequential; no new gain established.                                                                            |
| torrentdownloads | Deferred              | Generic markers are insufficient to validate a listing/detail rewrite. Potentially reducing 16 speculative listings to one is unmeasured and unshipped. |
| traht            | Deferred              | Captured browse output is empty; obtain a nonempty parser/download baseline first.                                                                      |
| uniondht         | Implemented           | First output is 78.9% earlier with five 100 ms pages; total time essentially unchanged. Order and ten unique rows are preserved.                        |
| xxxclubto        | Deferred              | Last live probe had no results; a usable baseline is required for the listing/detail pipeline.                                                          |
| yourbittorrent   | No material candidate | One listing response; no justified new gain.                                                                                                            |
| yts              | No material candidate | Known-page parallelism already shipped in v0.1.10; no additional gain credited.                                                                         |

## Validation on 2026-10-02

Static checks, generated-file audits, Python lint/type checks, installability,
and the website production build pass. Full deterministic suites on Python
3.9.6 and 3.11.15 each report 103 passing tests and five failures because this
environment cannot bind the local HTTP helper servers (`Bun.serve` reports
`EADDRINUSE` for port zero). The Python 3.9 compilation check uses a disposable
`PYTHONPYCACHEPREFIX` because the system interpreter's default cache directory
is outside the writable workspace.

The plugin quality audit reports zero errors and three warnings. The existing
Tokyo Toshokan warning concerns while-loop bounds. Two new Darklibria warnings reflect the analyzer's inability to infer bounds from
`range(len(self._path), ...)`; those loops traverse finite parser-list indices.

Focused required-result live runs attempted Elitetorrent (`inception`),
Darklibria (`the hobbit`), and UnionDHT (`ubuntu`). All failed to connect after
three attempts in the network-restricted environment. Live parser/download
behavior remains unverified here. The conditional pipeline, continuation, and
API-loop rewrites above are left deferred, and catalog health statuses are not
promoted from offline measurements.

## Runtime already present in v0.1.10

Each engine remains a standalone Python 3.9-compatible file. Its generated
runtime chooses `min(16, max(4, os.cpu_count() or 1))` workers, replacing the
fixed four-worker limit. A pool creates only as many workers as its initial
jobs need. The limit applies within each engine process; qBittorrent can run
several engine processes for one search.

Set `QBSEARCH_MAX_WORKERS` in the environment inherited by qBittorrent to
choose a different limit. Integer values are clamped to 1–16; invalid values
use the hardware default. For example, on a system where the executable is
available on `PATH`:

```sh
QBSEARCH_MAX_WORKERS=8 qbittorrent
```

The setting is read when the engine is imported. Restart qBittorrent after
changing its launch environment. Lower values can help when a remote service
limits requests or several engines are searching at once. Higher concurrency
can overlap independent HTTP requests, while server latency and availability
still determine much of the elapsed time.

## Runtime behavior

The canonical implementation is `tool/harden/safety_preamble.ts`; regenerate
all copies with `bun run gen -- --write --only harden`.

- `_qbt_iter_parallel` yields completed work as it becomes available. Its
  `ordered=True` mode preserves page or seed ordering with a bounded window of
  pending jobs and buffered results.
- `_qbt_run_parallel` eagerly consumes that iterator for existing engines whose
  workers print results themselves. Those searches still execute when callers
  ignore the returned list.
- Nested calls execute in their current worker instead of creating another
  pool. Darklibria collects remaining-page details before resolving them in one
  pool, so a search with few pages can still use its full detail worker budget.
- AudioBook Bay collects unique listing rows before parallel detail resolution
  and overlaps the remaining known search pages. Its HTML parser runs on the
  consuming thread.
- YTS fetches remaining known API pages concurrently and processes them in page
  order. A malformed page does not discard results from subsequent good pages.

HTTP timeouts, retries, response-size limits, page/detail limits, and locked
result printing remain in force. Closing an iterator stops consuming new jobs
and cancels queued work. Running requests finish under the existing timeout
policy; thread cancellation does not interrupt a request already in progress.

All 49 generated preambles were updated. Eighteen engines use the parallel
helpers, including the 16 existing pool users plus AudioBook Bay and YTS.
The remaining request sequences retain their single-response, pagination-stop,
next-link, rate-limit, or parser-state constraints. More workers do not imply
a speed improvement for every engine or query.

## Measurements on 2026-10-01

The baseline is release commit `af27a5d3cdd87b4c9c1624b763294b459a38048b`
(`v0.1.9`). Measurements used a host reporting 16 CPU cores and Python 3.9.6.
Throughput timings are medians of five runs. Artificial response delays isolate
the scheduling change from changing remote-site behavior.

| Workload                                                          | Baseline | Optimized | Speedup |
| ----------------------------------------------------------------- | -------: | --------: | ------: |
| Shared helper: 64 independent jobs, 30 ms delay each              | 543.0 ms |  138.5 ms |   3.92× |
| AudioBook Bay: eight pages, 32 unique details, 20 ms per response | 988.3 ms |  125.2 ms |   7.89× |
| YTS: eight API pages, 16 unique records, 20 ms per response       | 189.6 ms |   53.0 ms |   3.58× |
| Darklibria: two pages, 32 series details, 20 ms per response      | 248.0 ms |  103.3 ms |   2.40× |

Actual-engine benchmarks replayed the generated cases from
`test/support/concurrent_cases.ts` through `test/parser_harness.py`. Baseline
and optimized runs produced identical result dictionaries and requested the
same URL multiset: 41 requests for AudioBook Bay, eight for YTS, and 34 for
Darklibria. Peak overlapping requests rose from 1 to 16, 1 to 7, and 4 to 16,
respectively. Python 3.11.15 repeats measured 7.66×, 3.63×, and 2.42×.

In a separate shared-helper experiment with one 5 ms job and one 150 ms job,
the first result arrived in 6.4 ms instead of 151.0 ms. Streaming 64 results
of 512 KiB each reduced traced peak allocations from 32.0 MiB to 14.1 MiB.
These describe the controlled workloads, not a promise of equivalent gains
on live sites.

Full local reports, baseline sources, and benchmark scripts are ignored
artifacts under `working/performance/`. The deterministic regression suite
checks usable records, deduplication, page/detail bounds, request overlap,
ordering, malformed-page isolation, lazy input consumption, early iterator
closure, deadline handling, worker sizing, and nested pool avoidance. It checks
overlap rather than enforcing elapsed-time thresholds.

## Live evidence

The initial all-plugin sweep tested all 49 engines with required result markers:
25 passed and 24 failed. A later sweep after the shared runtime change probed
47 engines outside the Bitsearch/Solid Torrents backend: 23 passed and 24 failed,
with the same failing IDs. Five endpoints returned HTTP 522, Tokyo Toshokan
returned HTTP 403, and 18 responses had no generic result markers.

Fresh actual-parser passes for Bitsearch and Solid Torrents each emitted 40
usable records for both of their public queries. A subsequent Solid Torrents
marker probe returned HTTP 429, so both shared-backend checks stopped. Those
two engines remain `intermittent`, and their source changes require renewed
recovery evidence before promotion. See `MAINTENANCE_LOG.md` for current hashes,
capture paths, and the pending follow-up dates.

The focused Darklibria marker probe after its pool restructuring also found
no markers for `the hobbit`. Fresh actual-parser captures produced three usable
YTS records for `inception`; AudioBook Bay's `the hobbit` capture timed out, and
Darklibria's HTTP 200 response for that query emitted no records.
Marker probes inspect remote HTTP responses;
they do not execute the Python parser or verify torrent downloads. Offline
performance gains do not repair unavailable or changed remote services.
