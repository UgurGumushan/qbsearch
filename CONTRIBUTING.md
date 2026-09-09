# Contributing and maintaining

If you want to change or maintain qbsearch itself, this is the maintainer guide.
For plugin install and end-user usage, use the main [README.md](README.md).

## Repository structure

- `plugins/` contains standalone qBittorrent engine files (Python 3.9+ compatible), each installable on its own.
- `catalog/plugins.json` is the metadata source of truth for all plugin IDs, links, status, and categories.
- `documentation/PLUGINS.md` and other generated docs are generated from catalog data.
- `documentation/MAINTENANCE_LOG.md` records status transitions and probe evidence across sweeps.
- `tool/` is the maintainer command layer:
  - `tool/cli.ts` routes all commands.
  - `tool/core/` contains shared helpers.
  - `tool/commands/`, `tool/generators/`, and worker modules (`catalog`, `checks`, `harden`, `icons`, `release`) implement maintainers flows.
- `test/` includes Bun tests, live-test workers, and Python compatibility harnesses.
- `install/` contains native installers for macOS, Linux, and Windows.
- `packages/website` is the distribution website package.
- `documentation/` is generated and checked; avoid hand editing generated markdown.

## Command reference

Use Bun scripts from the repository root:

```sh
bun run setup
bun run check
bun run check -- --fast
bun run gen -- --check
bun run gen -- --write
bun run plugin -- --validate
bun run plugin -- --new <id> --kind json|html --site https://example.com
bun run test
bun run test -- --watch
bun run test -- --live
bun run test -- --live --plugin <plugin-id>
bun run test -- --live --plugin <plugin-id> --require-results
bun run release -- 0.1.3
```

Notes:

- `check` is the full deterministic gate and does not contact remote torrent sites.
- `check -- --fast` runs the static/generated subset used by pre-commit.
- `gen -- --check` validates generated artifacts without writing.
- `test -- --live` makes network requests.

## Install runtime prerequisites

Run once per clone:

```sh
bun run setup
```

This installs pinned tool dependencies and enables the repository pre-commit hook.

## Making plugin changes

### Change an existing plugin

1. Edit `plugins/<plugin-id>.py`.
2. Preserve the qBittorrent contract and keep `# VERSION:` valid.
3. Update `catalog/plugins.json` if site, category, default query, status, or notes changed.
4. Regenerate catalog docs:
   ```sh
   bun run gen -- --write --only catalog
   ```
5. Run offline checks:
   ```sh
   bun run check -- --fast
   ```
6. If endpoint parsing changed, run a focused live sweep:
   ```sh
   bun run test -- --live --plugin <plugin-id>
   ```
   Add `--require-results` when expected results are a must.

## Plugin quality and performance contract

Every engine must keep network work bounded and remain independently
installable. In addition to preserving metadata and result fields:

- Use the generated safety helpers for network access, retries, deadlines,
  and parallel work.
- Keep pagination and detail resolution within `MAX_PAGES` and `MAX_DETAILS`.
- Avoid fixed sleeps, duplicate requests, repeated parsing, and unbounded
  result or response-body accumulation.
- Do not disable TLS certificate verification or introduce raw threads.
- Deduplicate URLs before detail requests and stop when a service signals that
  no more results are available.
- Keep plugin-specific behavior outside the generated safety preamble; update
  the preamble source and regenerate when shared behavior changes.

The deterministic check reports transport, loop, concurrency, and dead-code
violations across every plugin. Live checks remain necessary for endpoint
behavior, but remote availability is not used as a deterministic performance
gate.

### Add a new plugin

1. Scaffold the engine file:
   ```sh
   bun run plugin -- --new <id> --kind json --site https://example.com
   ```
2. Inject generated safety preamble:
   ```sh
   bun run gen -- --write --only harden
   ```
3. Add the matching icon under `icons/<id>.ico` when available.
4. Add one catalog record in `catalog/plugins.json`.
5. Regenerate all generated docs/checks:
   ```sh
   bun run gen -- --write
   ```

## Maintenance health loop

Run this cycle when triaging a maintenance batch:

1. Generate the non-active candidate list:
   ```sh
   node - <<'NODE'
   const fs = require("fs");
   const plugins = JSON.parse(fs.readFileSync("catalog/plugins.json", "utf8")).plugins;
   const buckets = { unavailable: [], intermittent: [], retired: [] };
   for (const [id, plugin] of Object.entries(plugins)) {
     const status = plugin.status ?? "active";
     if (buckets[status]) {
       buckets[status].push(id);
     }
   }
   console.log("non_active:", JSON.stringify(buckets, null, 2));
   NODE
   ```
2. Probe each non-active candidate with a focused live check:
   ```sh
   bun run test -- --live --plugin <id>
   ```
3. Repeat any flaky candidate until behavior is stable, then adjust:
   - `unavailable` -> `intermittent` requires >= 2 clean runs in a row.
   - `intermittent` -> `active` requires >= 3 clean runs on separated passes.
   - Never mark `retired` as `active` without a positive run history and intent.
4. Record each status change in `documentation/MAINTENANCE_LOG.md` before you edit
   `catalog/plugins.json`.

## Validation and checks

### Deterministic checks (offline)

```sh
bun run check
```

`check` includes TypeScript, lint, Python syntax/build checks, catalog validation, generated-file audits, and installability checks.

### Live service checks

```sh
bun run test -- --live
bun run test -- --live --plugin <id>
bun run test -- --live --content-category <category>
bun run test -- --live --query <query>
bun run test -- --live --require-results
```

Guidance:

- `intermittent`, `unavailable`, and `retired` catalog entries are skipped in default live runs.
- Use `--plugin` to force-check skipped entries.
- Avoid sensitive search terms in live checks.

### Generated files governance

```sh
bun run gen -- --check
bun run gen -- --check --strict
```

is required whenever plugin/catalog changes are introduced. It verifies:

- `documentation/PLUGINS.md`
- safety preamble injection state
- CLI docs
- probe URL fixtures
- plugin source manifest

Use `--strict` to fail checks on missing `license`/`notes` metadata so hygiene debt
must be resolved before release.

### Catalog metadata hygiene

Before each maintenance batch, run:

```sh
node - <<'NODE'
const fs = require("fs");
const plugins = JSON.parse(fs.readFileSync("catalog/plugins.json", "utf8")).plugins;
const lackingLicense = plugins.filter((entry) => !entry.license || entry.license === "None");
const missingNotes = plugins.filter((entry) => !(entry.notes || "").trim());
console.log("missing_license", lackingLicense.length);
console.log("blank_notes", missingNotes.length);
NODE
```

Use this as a gap list for non-functional metadata updates to keep operator guidance accurate.

## Release process

Build release artifacts with:

```sh
bun run release -- <version>
```

This collects installers, plugin files, icons, support JSON, and docs into the distributable zip.

## Maintenance backlog

When you plan a maintenance cycle, include these follow-up tasks:

1. Re-evaluate non-active status buckets

- Re-check all `unavailable`, `intermittent`, and `retired` plugins with focused live probes.
- Keep status aligned to observed behavior and avoid forcing active status without evidence.

2. Catalog metadata hygiene

- Improve missing metadata in `catalog/plugins.json` (`license`, `notes`) where the source is known.
- Keep `notes` concise and useful for operators.

3. Plugin scaffold quality

- Audit `bun run plugin -- --new` output in `tool/commands/plugin.ts` and consider improving placeholder/default generation quality before accepting future scaffolds.

4. Operational health tracking

- Add explicit periodic triage notes for flaky/blocked services.
- Record why entries changed status to reduce silent regressions.

5. Release/documentation alignment

- Keep changelog entries, release notes, and generated artifacts in sync during every version bump.

## Pull request checklist

- List changed plugins and catalog updates.
- Include live query and outcome when endpoint behavior changed.
- Mention commands run (`check`, `test`, and any live checks).
- Do not commit credentials, session cookies, or private data.
- Keep changes focused to one maintenance objective.
