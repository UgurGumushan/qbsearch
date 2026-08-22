# qbsearch website

The public distribution site for the qBittorrent nova3 plugin collection.

## Run locally

From the repository root:

```sh
bun install
bun --cwd packages/website dev
```

The app reads the checked-in `catalog/plugins.json` file at build time, so the
website directory should be deployed with the repository checkout available.
For Vercel, set the project root directory to `packages/website` and use Bun as
the package manager. The app's `next.config.ts` keeps the repository root in
the file-tracing boundary for the catalog read.

## Release downloads

`/download/latest` resolves the latest ZIP asset from the GitHub Release API.
The release workflow also uploads a stable `qbsearch-latest.zip` alias beside
the versioned archive for direct download links.
