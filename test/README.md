# Test layout

Bun owns the deterministic test suite. The files in this directory contain
Bun test modules, live-test workers, and the small Python compatibility
harnesses that must import qBittorrent plugins under Python:

- `fixtures/` contains deterministic cross-runtime assets, including the
  Python script used to exercise generated safety helpers;
- `live.ts` coordinates live-service cases and launches the TypeScript
  `live_plugin.ts` worker for each plugin. Its `live/` modules separate CLI
  parsing, catalog selection, process orchestration, source inspection, and
  HTTP/result handling;
- `live_plugin.ts` is the stable worker entrypoint and public import surface;
  its implementation lives in `live/` so the source contract and HTTP helpers
  can be exercised independently;
- `live_safety.ts` owns the deterministic TypeScript helper and contract suite;
- `safety.ts` is imported by the Bun repository tests for the offline generated
  preamble and fake-server checks. The audit and Python compatibility pieces
  live in `safety/`;
- `engines.py` is a thin command adapter for the separate offline qBittorrent
  installability harness in `engine_harness.py`;
- `plugin_sources.ts` statically imports every plugin as text. This makes each
  standalone `.py` engine an explicit Bun watch dependency without changing
  how qBittorrent installs it;
- `support/` contains shared repository paths, subprocess execution, and
  catalog/plugin-inventory checks;
- `repository.test.ts` is the Bun-owned deterministic repository test suite.

Run the supported commands from the repository root:

```sh
bun test
bun run test:watch
bun run check
bun run test:live -- --plugin <plugin-id>
bun run test:live:watch -- --plugin <plugin-id>
```

`bun run test:watch` is the persistent local workflow. It runs Bun's test
runner with `--watch`; edits to any existing file under `plugins/` rerun the
repository tests because `plugin_sources.ts` imports those files as text. When
adding a plugin, add its import to that manifest so it is watched as well.

The live suite and its helper suite are Bun/TypeScript-only. The deterministic
repository suite still launches the Python compatibility harnesses from inside
Bun tests where it must exercise the same Python runtime qBittorrent uses.

The coordinator probes active catalog entries by default. Entries marked
`intermittent`, `unavailable`, or `retired` are retained for explicit focused
checks but skipped from the default remote run.

`bun run test:live:watch` runs the same coordinator under Bun's process watcher
and reruns it when a plugin source or the catalog changes. It makes real remote
requests on every run, so use a focused `--plugin` selection while iterating.
