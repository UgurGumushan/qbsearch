# Repository Guidelines

## Project Structure

- `plugins/` contains standalone qBittorrent nova3 search engines. Each file
  must work when installed without a repository runtime package.
- `icons/` stores matching plugin icons; `catalog/plugins.json` is the metadata
  source of truth and `documentation/PLUGINS.md` is generated from it.
- `documentation/` contains installation, catalog, attribution, and changelog
  documentation; GitHub-facing `README.md`, `CONTRIBUTING.md`, and `LICENSE.md`
  remain at the repository root.
- `check/` contains repository check entrypoints and check-only catalog and
  plugin audits.
- `generate/` contains catalog, hardening, icon, and upstream generators.
- `release/` contains the release archive builder.
- `scripts/` contains the shared Bun command router, setup command, repository
  paths, process helpers, and small common utilities. Image conversion uses the
  Bun-compatible `cross-image` package.
- `test/` contains the Bun test suite, the TypeScript live smoke-test workers,
  and the small Python compatibility harnesses used only by offline
  installability checks.
- `typings/` contains stubs for qBittorrent modules unavailable on the host.
  `external/` is vendored upstream material and is not maintained directly.

## Build, Test, and Development Commands

```sh
bun run setup                           # Install pinned tools and enable hooks
bun run check                           # Run deterministic repository checks
bun run test:watch                      # Keep Bun tests watching plugins/
bun run format                          # Format supported non-Python text
bun run harden -- --check               # Audit generated plugin safety helpers
bun run icons                           # Refresh plugin icons
bun run test:live -- --plugin yts       # Run one live plugin test
bun run test:live:watch -- --plugin yts # Rerun one live test on source changes
bun run test:live                       # Query all configured remote sites
bun run release -- 0.1.3                # Build working/qbsearch-0.1.3.zip
```

`bun run check` validates generated files, safety helpers, compilation,
installability, TypeScript, ESLint, Prettier, Ruff, and BasedPyright. Live tests
make real HTTP requests through Bun; use focused runs while developing parsers.
For iterative plugin work, keep `bun run test:watch` running; the Bun test
manifest imports every plugin as text so changes under `plugins/` rerun the
repository checks.

## Coding Style and Naming

Use Python 3.9-compatible syntax and four-space indentation. Ruff is configured
for a 100-character line length; run `bun run static-check` or `ruff format` and
`ruff check`. Keep plugin filenames, classes or aliases, and catalog IDs
aligned (`plugins/<plugin-id>.py`). Preserve each plugin’s `#VERSION:` line,
qBittorrent result schema, and generated safety preamble. Do not introduce
imports from a shared repository runtime into standalone engines.

## Testing Guidelines

There is no coverage threshold. Add or update deterministic checks in the
existing safety suite when changing shared helper behavior. For parser or
endpoint changes, run `bun run test:live -- --plugin <plugin-id>` and record
the query and remote outcome. Use `--require-results` when empty results should
be considered a failure.

## Commits and Pull Requests

Use concise imperative commit subjects, consistent with history (for example,
`Update RARBG plugin for JSON search API`). Keep changes focused. Pull requests
should identify affected plugins, describe observed remote behavior, list
commands run, and mention catalog or generated-file updates. Never commit
credentials, cookies, tokens, or sensitive live-search queries.
