# Contributing and maintaining

The installable engines remain flat, standalone `.py` files in `plugins/`.
Do not add imports from a repository runtime package to an engine: qBittorrent
installs a selected file without the rest of this checkout.

Repository automation is run through Bun. Icon generation uses the
`cross-image` JavaScript package; invoke all repository workflows through the
Bun commands below.

The test suite and compatibility harnesses live under `test/`; use the Bun
commands below rather than relying on their internal filenames. Live testing
is TypeScript-only; the Python harnesses are retained for offline checks that
must import qBittorrent plugins.

The public maintenance entrypoint is `scripts/commands.ts`, exposed through
the package scripts. Check workers live under `check/`, generators under
`generate/`, and release packaging under `release/`; `scripts/` contains only
the shared command router and orchestration helpers. The Python compatibility
harnesses remain under `test/` because they must import qBittorrent's Python
modules and plugins.

The collection installers live in `install/`. Keep `macos.sh` and `linux.sh`
POSIX-shell-only and `windows.ps1` PowerShell-only: they must install the full
collection without Python, Bun, command-line options, or user-specific
configuration. Existing support JSON files must never be overwritten. The
maintainer importer writes raw upstream snapshots to `external/upstream/` so it
cannot overwrite the hardened files users install. Review upstream changes and
port them into `plugins/` deliberately.

## Change an existing plugin

1. Edit `plugins/<plugin-id>.py`.
2. Keep the qBittorrent result schema and `#VERSION:` line valid.
3. Update the matching record in [`catalog/plugins.json`](catalog/plugins.json)
   if the site, category, default query, status, provenance, or notes changed.
4. Regenerate the human-readable index:

   ```sh
   bun run catalog
   ```

5. Run the offline checks below.
6. Run a focused live search when the change affects a parser or endpoint:

   ```sh
   bun run test:live -- --plugin <plugin-id>
   ```

## Add a plugin

Add exactly these files:

- `plugins/<plugin-id>.py`, with a class or alias named `<plugin-id>`;
- `icons/<plugin-id>.ico`, unless an icon is intentionally unavailable;
- one catalog record with a conservative default query.

The catalog checker catches missing records, stale class metadata, missing
icons, duplicate IDs, invalid categories, and invalid statuses.

## Offline checks

```sh
bun run check
```

This runs the deterministic Bun test suite, TypeScript, ESLint, Prettier, Ruff,
BasedPyright, catalog validation, generated safety checks, deterministic
fake-server tests, Python compilation, and the qBittorrent installability
harness. It does not contact remote torrent sites.

For iterative plugin changes, use Bun's watch runner:

```sh
bun run test:watch
```

The test source manifest imports every existing `plugins/*.py` file as text, so
editing an engine reruns the repository tests. When adding a plugin, add its
text import to `test/plugin_sources.ts` so the new file is watched too.

## Automatic static checks

Install the pinned development tools and enable the repository's tracked
pre-commit hook once per clone:

```sh
bun run setup
```

After that, every `git commit` runs the same static checks used by CI. Run only
those checks manually with:

```sh
bun run static-check
```

The individual checks are also available as `bun run typecheck`, `bun run lint`,
`bun run format:check`, and `bun run python:check`. Use `bun run format` when
you want Prettier to rewrite supported non-Python text files.

The hook is stored in `.githooks/`, so it remains reviewable and consistent
across maintainers. CI still runs `bun run check` as the authoritative check for
clones where local hooks have not been enabled.

## Live checks

```sh
bun run test:live
bun run test:live -- --plugin yts --require-results
bun run test:live -- --content-category anime
bun run test:live:watch -- --plugin yts
```

These commands make actual requests for active catalog entries. Each engine
runs in its own Bun/TypeScript subprocess, and the coordinator uses one worker
per logical CPU. Remote outages, rate limits, Cloudflare challenges, and
changed HTML should be recorded in the catalog or an issue rather than hidden
by changing the parser blindly. Entries marked `intermittent`, `unavailable`,
or `retired` are skipped by the default run; use `--plugin ID` to investigate
one explicitly.

The live suite accepts an empty result-marker set by default. Use
`--require-results` when investigating a particular site. A successful HTTP
request with zero markers is different from a malformed plugin contract, an
exception, or zero observed requests; those remain failures.
`test:live:watch` keeps the same options and reruns the live checks when a
plugin source or the catalog changes.

## Catalog and generated files

`catalog/plugins.json` is the metadata source of truth.
`documentation/PLUGINS.md` is generated and should not be hand-edited. To
validate the pair:

```sh
bun run catalog -- --check
```

The safety preamble in the engines is generated and audited by the TypeScript
worker behind `bun run harden`. Run its checker after changing generated engine
code:

```sh
bun run harden -- --check
```

Release archives include all three native installers and the plugin support
JSON files. Verify them with the TypeScript release entrypoint:

```sh
bun run release -- --version dev --output working/qbsearch-dev.zip
```

## Pull requests

Keep pull requests focused. Include the affected plugin ID, the remote
behavior observed, the query used, and whether the parser was checked against
a saved fixture or a live service. Do not commit credentials, cookies, or
personal search queries.
