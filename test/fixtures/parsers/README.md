# Parser response fixtures

These public HTML samples were captured through Bun on 2026-10-01 and replayed
through the actual standalone Python engines. They use the queries `inception`
and `matrix`; the Bitsearch and Solid Torrents recovery checks also use `ubuntu`.

- Bitsearch responses came from `https://bitsearch.to/search?q=inception&page=1`
  and page 2, both redirected to `bitsearch.eu`. Each fixture page retains the
  original result-count banner and the first two complete result cards.
- Elitetorrent responses came from `https://www.elitetorrent.com/?s=inception`
  and `?s=matrix`, their `/page/1/` forms, and the linked detail pages. The fixtures
  retain the search banner and the first two result cards, plus the corresponding
  detail titles, metadata, and encoded download anchors.
- Solid Torrents responses came from `https://solidtorrents.to/search?q=ubuntu&page=1`
  and page 2, both redirected to `bitsearch.eu`. Each fixture page retains the
  original result-count banner and the first two complete result cards, including
  duplicate mobile/desktop download anchors and nested metadata spans. These pages
  reproduced zero results in the old engine before the parser repair.

Advertising, scripts, images, SVG icons, and unrelated page sections were omitted.
The original result-count banners remain; `maxPages` and `maxDetails` explicitly
bound fixture replay. Expected records preserve captured metadata except for exact
publication timestamps for Bitsearch and Elitetorrent, which derive them using the
host's local timezone. Solid Torrents uses UTC for both legacy and current date
formats, so its fixture includes exact publication timestamps.

The additional edge cases in the Bun tests derive from these samples or use small
synthetic documents. The offline harness always installs qBittorrent stubs and blocks
network and download calls, even when the host has a real qBittorrent profile.
