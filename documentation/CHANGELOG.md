# Changelog

## 0.1.10

- Scale parallel search work from four workers to a hardware-based 4–16 worker
  default, with a `QBSEARCH_MAX_WORKERS` environment override clamped to 1–16.
- Stream completed results, preserve page and seed ordering where required,
  bound queued work and response buffering, and prevent nested pools from
  multiplying active requests.
- Parallelize AudioBook Bay detail resolution and known pagination, overlap
  YTS API pages, and restructure Darklibria's page/detail scheduling.
- Add deterministic concurrency and actual-parser regression checks. Controlled
  benchmarks retain identical output and request counts while improving
  AudioBook Bay, YTS, and Darklibria throughput by 7.89×, 3.58×, and 2.40×.
- Document worker configuration, benchmark assumptions, all-plugin live
  outcomes, and current-source recovery follow-ups. Keep Bitsearch and Solid
  Torrents intermittent after the shared backend returned HTTP 429.
- Include the performance guide and current maintenance evidence in the ZIP.

## 0.1.9

- Put the latest ZIP download, platform installation steps, and all 49 plugin
  downloads directly in the README, grouped by category with catalog statuses.
- Correct the Python prerequisite, remove a retired troubleshooting command,
  and use shell installer commands that work from an extracted release archive.
- Allow bounded functional-capture tests to finish on slower CI runners and
  narrow the parser harness loader type explicitly for Python 3.9 checks.

## 0.1.8

- Restore Elitetorrent encoded magnet extraction and Solid Torrents parsing for
  its current redirected listing; preserve standalone Python 3.9 compatibility.
- Verify initial Bitsearch and Solid Torrents recovery with actual-parser replay.
  Keep both intermittent until separated-day promotion checks are complete.
- Repair Pirateiro desktop row parsing, global result caps, and escaped magnet
  resolution. Its listing smoke probe passes; live detail downloads remain
  unverified because of timeouts.
- Add bounded Bun capture and offline actual-engine/download replay for Ali213,
  Pirateiro, and Traht, with binary torrent metadata validation, Windows-1251
  decoding, source hashes, and preserved HTTP 429/cooldown evidence.
- Improve conservative plugin-quality analysis, resolving 37 of 39 advisory
  warnings; retain two manually reviewed warnings for unproven loop progress.
- Harden JSON/HTML scaffolds and option validation, retry-helper use, duplicate
  handling, malformed-row tolerance, and result limits.
- Audit all 26 unresolved upstream licenses; verify eleven catalog labels and
  package their exact license notices. Document fifteen unresolved dispositions.
- Refresh generated documentation and record current recovery failures and
  manual follow-up dates. Retain all 49 engines pending the two-date removal
  policy.

## 0.1.7

- Improve plugin search bounds, duplicate handling, parser resilience, and
  deadline-aware networking while preserving standalone Python 3.9 support.
- Add deterministic plugin quality checks and maintenance evidence validation.
- Make the README installation-focused and consolidate contributor guidance.
- Remove 12 engines after unsuccessful live probes: anidex, calidadtorrent,
  cloudtorrents, glotorrents, goggames, kickasstorrents, magnetdl, mejortorrent,
  redetorrent, rockbox, torrentgalaxy, and yggtracker. The catalog now contains
  49 engines. Observed failures included HTTP errors, access blocks, connection
  failures, and timeouts; these do not establish permanent site failure.
- Refresh generated catalog documentation, plugin sources, and probe fixtures.

## 0.1.6

- Triaged the weekly live sweep: retired goggames, marked three dead sites as
  unavailable until they return, and moved mikanani to its new domain.
- Added offline probe-URL fixtures (`test/live/fixtures/probe-urls.json`) with
  drift detection, so live probe targets no longer depend on a network pass.
- Reduced the command surface to six commands (`setup`, `check`, `gen`,
  `plugin`, `test`, `release`); legacy aliases are rejected.
- Moved all repository workers into `tool/` behind a single shared core and
  wire `gen -- --check` into `check -- --fast` so the pre-commit hook audits
  generated files as documented.
- Removed deprecated `test/support/` shims and the unused upstream provenance
  importer; provenance lives in catalog `source_url` fields.

## 0.1.5

- Added a catalog-driven Next.js distribution website under `packages/website`
  with responsive installation guidance, plugin search, category filters, and
  links to the maintained source catalog.
- Added a `/download/latest` release resolver so the website sends users to the
  ZIP built by the GitHub Actions release workflow.
- Added a stable `qbsearch-latest.zip` asset alongside each versioned release
  archive for durable website download links.
- Added the website as a Bun workspace package with pinned Next.js and React
  dependencies.

## 0.1.4

- Added a catalog-driven user installation and plugin discovery workflow.
- Added cross-platform collection installers and release ZIP packaging.
- Replaced the Python collection installer with dependency-free native scripts
  under `install/` and removed the obsolete compatibility wrappers.
- Added generated plugin documentation and maintainer guidance.
- Moved live-test default queries out of the test runner and into the catalog.
- Replaced Make-based maintainer commands with a Bun command surface and Bun test runner.
- Migrated live plugin smoke tests and their helper suite to TypeScript/Bun;
  live checks no longer start Python processes.
- Consolidated shared process and catalog tooling, and corrected the public
  documentation directory name to `documentation/`.

## 0.1.3

- Hardened all plugin engines and support tooling for strict linting and type checking while preserving qBittorrent Python 3.9 compatibility.
- Added safer live-test adapters and runtime validation across the plugin collection.
- Fixed live testing for AnimeTosho feeds that omit peer counts.

## 0.1.2

- Updated the RARBG plugin for the JSON search API.
- Added published-date extraction to a dozen engines across anime, general,
  and movie categories.
- Added a qBittorrent Search tab screenshot to the README.

## 0.1.1

- Fixed the Python checker environment used by the release workflow.
- No plugin engine changes.
