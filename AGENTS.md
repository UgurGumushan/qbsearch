# Repository Guidelines

## Project Structure

- `plugins/` contains standalone qBittorrent nova3 search engines. Each file
  must work when installed without a repository runtime package.
- `icons/` stores matching plugin icons; `catalog/plugins.json` is the metadata
  source of truth and `PLUGINS.md` is generated from it.
- `scripts/` contains catalog, safety, live-test, hardening, and release tools.
- `typings/` contains stubs for qBittorrent modules unavailable on the host.
  `external/` is vendored upstream material and is not maintained directly.

## Build, Test, and Development Commands

```sh
make dev-setup                         # Install pinned tools and enable hooks
make check                             # Run deterministic repository checks
./test_all_plugins.sh --plugin yts     # Run one live plugin test
./test_all_plugins.sh                  # Query all configured remote sites
make release VERSION=0.1.3             # Build working/qbsearch-0.1.3.zip
```

`make check` validates generated files, safety helpers, compilation,
installability, Ruff, and BasedPyright. Live tests make real HTTP requests;
use focused runs while developing parsers.

## Coding Style and Naming

Use Python 3.9-compatible syntax and four-space indentation. Ruff is configured
for a 100-character line length; run `make static-check` or `ruff format` and
`ruff check`. Keep plugin filenames, classes or aliases, and catalog IDs
aligned (`plugins/<plugin-id>.py`). Preserve each plugin’s `#VERSION:` line,
qBittorrent result schema, and generated safety preamble. Do not introduce
imports from a shared repository runtime into standalone engines.

## Testing Guidelines

There is no coverage threshold. Add or update deterministic checks in the
existing safety suite when changing shared helper behavior. For parser or
endpoint changes, run `./test_all_plugins.sh --plugin <plugin-id>` and record
the query and remote outcome. Use `--require-results` when empty results should
be considered a failure.

## Commits and Pull Requests

Use concise imperative commit subjects, consistent with history (for example,
`Update RARBG plugin for JSON search API`). Keep changes focused. Pull requests
should identify affected plugins, describe observed remote behavior, list
commands run, and mention catalog or generated-file updates. Never commit
credentials, cookies, tokens, or sensitive live-search queries.
