# qbsearch website

The download page for the qBittorrent search plugin collection. It contains one
ZIP download link, installation commands, and links to the repository documentation.

## Run locally

From the repository root:

```sh
bun install
bun run --cwd packages/website dev
```

The homepage is static and uses native links, so downloading works with
JavaScript disabled. It does not read the catalog or call the GitHub API.
The plugin list lives in `documentation/PLUGINS.md`.

For Vercel, set the project root directory to `packages/website` and use Bun as
the package manager. Deploy from the repository checkout: the workspace manifest,
lockfile, and Bun dependency layout are shared with the root. The app's
`next.config.ts` includes the repository root in the file-tracing boundary.

To build the production app:

```sh
bun run --cwd packages/website build
```

## Release downloads

The Download ZIP link points directly to:

```text
https://github.com/UgurGumushan/qbsearch/releases/latest/download/qbsearch-latest.zip
```

`/download/latest` remains available for existing links and returns an HTTP 307
redirect to the same URL without making a network request. Both use
`lib/links.ts`.

The release workflow must continue uploading `qbsearch-latest.zip` beside the
versioned archive. GitHub resolves the stable link to the latest release asset,
so the website does not need a version update for each release.
