# Contributing and maintaining

The installable engines remain flat, standalone `.py` files in `plugins/`.
Do not add imports from a repository runtime package to an engine: qBittorrent
installs a selected file without the rest of this checkout.

The old `download_and_test.sh` command is only a compatibility wrapper. The
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
   python3 scripts/generate_plugin_catalog.py --docs
   ```

5. Run the offline checks below.
6. Run a focused live search when the change affects a parser or endpoint:

   ```sh
   ./test_all_plugins.sh --plugin <plugin-id>
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
make check
```

This runs catalog validation, generated safety checks, deterministic
fake-server tests, Python compilation, the qBittorrent installability
harness, Ruff, and BasedPyright. It fails if either static checker is
unavailable; checks are never silently skipped. It does not contact remote
torrent sites.

## Automatic static checks

Install the pinned development tools and enable the repository's tracked
pre-commit hook once per clone:

```sh
make dev-setup
```

After that, every `git commit` runs the same Ruff and BasedPyright checks used
by CI. Run only those checks manually with:

```sh
make static-check
```

The hook is stored in `.githooks/`, so it remains reviewable and consistent
across maintainers. CI still runs `make check` as the authoritative check for
clones where local hooks have not been enabled.

## Live checks

```sh
./test_all_plugins.sh
./test_all_plugins.sh --plugin yts --require-results
./test_all_plugins.sh --content-category anime
```

These commands make actual requests. Each engine runs in its own subprocess,
and the coordinator uses one worker per logical CPU. Remote outages, rate
limits, Cloudflare challenges, and changed HTML should be recorded in the
catalog or an issue rather than hidden by changing the parser blindly.

The live suite accepts an empty result set by default. Use `--require-results`
when investigating a particular site. A successful HTTP request with zero
records is different from a malformed result, an exception, or zero observed
requests; those remain failures.

## Catalog and generated files

`catalog/plugins.json` is the metadata source of truth. `PLUGINS.md` is
generated and should not be hand-edited. To validate the pair:

```sh
python3 scripts/generate_plugin_catalog.py --check
```

The safety preamble in the engines is generated and audited by
`scripts/harden_plugins.py`. Run its checker after changing generated engine
code:

```sh
python3 scripts/harden_plugins.py --check
```

## Pull requests

Keep pull requests focused. Include the affected plugin ID, the remote
behavior observed, the query used, and whether the parser was checked against
a saved fixture or a live service. Do not commit credentials, cookies, or
personal search queries.
