# Architecture

## Command layer (`tool/`)

All repository automation runs through one router, `tool/cli.ts`, exposed as
six package scripts: `setup`, `check`, `gen`, `plugin`, `test`, `release`.
`documentation/CLI.md` is rendered from the router table, so `--help` output
and docs cannot drift apart.

- `tool/core/repo.ts` — paths and TypeScript roots (`TYPESCRIPT_DIRS`, the
  source of truth for `tsconfig.json` and `eslint.config.js`).
- `tool/core/run.ts` — the only process runner (inherit-io, captured with
  timeout, parallel task fan-out, `QBSEARCH_PYTHON` resolution).
- `tool/core/plugins.ts` — the only plugin discovery (disk scan + catalog
  join + inventory agreement check).
- `tool/core/python-parse.ts` — the only Python-source parser (`#VERSION:`,
  engine class/alias, `name`/`url`, search method).
- `tool/commands/` — thin CLI adapters over the workers below.
- `tool/generators/` — pure renderers (watch manifest, CLI docs).

Domain workers live in matching directories (`tool/catalog/`, `tool/harden/`,
`tool/icons/`, `tool/upstream/`, `tool/checks/`, `tool/release/`) and share
`tool/core/`. New shared code goes in `tool/core/`.

## Check modes

- `check --fast`: TypeScript, ESLint, Prettier, Ruff, BasedPyright, plus
  `gen --check` (catalog, preambles, watch manifest, CLI docs). This is what
  the pre-commit hook runs.
- `check --full` (default): `--fast` plus the deterministic `bun test` suite,
  which adds catalog validation, preamble audits, Python compilation, the
  qBittorrent installability harness, and the fake-server safety suite.

CI runs the full gate on Python 3.9 and 3.11, then builds the website.

## Plugins

`plugins/<id>.py` files are standalone: qBittorrent installs one file without
the rest of the checkout, so engines must not import repository code. Each
engine carries a generated safety preamble between
`# BEGIN/END GENERATED QBITT SAFETY PREAMBLE` markers providing bounded
retries, timeouts, thread-pool parallelism, and locked result printing with
stdlib only (Python 3.9 compatible).

Authoring flow: `plugin -- --new <id>` scaffolds a slim engine with a
`# QBSEARCH-PREAMBLE-ANCHOR` line; `gen -- --write --only harden` inserts the
preamble there (or replaces it in place for existing engines).
`catalog/plugins.json` is the metadata source of truth; `PLUGINS.md` and
`test/plugin_sources.ts` are generated from disk + catalog.

## Live tests

`test -- --live` probes real sites through isolated Bun workers using each
plugin's catalog query. Empty results are allowed by default (site reachable,
no matches); `--require-results` turns them into failures. Probes never use
sensitive queries.
