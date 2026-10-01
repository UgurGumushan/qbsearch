# Search performance

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
