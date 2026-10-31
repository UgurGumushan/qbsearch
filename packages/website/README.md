# qbsearch website

A static download page with installation commands and repository links. Edit
`public/index.html`, `public/styles.css`, and `public/icon.svg` directly. No build,
package installation, or JavaScript is required.

## Preview locally

From the repository root:

```sh
python -m http.server 3000 --bind 127.0.0.1 --directory packages/website/public
```

Open <http://localhost:3000>. The simple file server previews the page and assets;
Vercel handles the compatibility redirect described below.

## Deploy

Keep the Vercel project root at `packages/website`. `vercel.json` selects the
Other framework preset, skips installation and building, and serves only `public/`.
The root formatter and `bun run test` cover the page's download contract.

## Release downloads

The Download ZIP link points directly to the stable GitHub release asset:

```text
https://github.com/UgurGumushan/qbsearch/releases/latest/download/qbsearch-latest.zip
```

`/download/latest` remains an HTTP 307 redirect to that same URL, configured in
`vercel.json`. Verify both links in a Vercel preview when changing deployment
configuration. The release workflow continues uploading `qbsearch-latest.zip`
beside the versioned archive, so the page requires no per-release updates.
