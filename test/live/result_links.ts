/** Elitetorrent repeats each result's image/title link inside this list. */
export function elitetorrentResultLinks(body: string, siteUrl: string): string[] {
  const links = new Set<string>();
  const lists = body.matchAll(
    /<ul\b[^>]*\bclass\s*=\s*(?:"[^"]*\bminiboxs-ficha\b[^"]*"|'[^']*\bminiboxs-ficha\b[^']*'|miniboxs-ficha(?=\s|>))[^>]*>([\s\S]*?)<\/ul>/gi,
  );
  const origin = new URL(siteUrl).origin;
  for (const list of lists) {
    const anchors = list[1].matchAll(/<a\b[^>]*\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi);
    for (const anchor of anchors) {
      try {
        const href = anchor.slice(1).find(Boolean) ?? "";
        const url = new URL(href.replaceAll("&amp;", "&"), siteUrl);
        if (url.origin === origin && /^\/(?:peliculas|series)\/[^/]+\/$/.test(url.pathname)) {
          links.add(url.href);
        }
      } catch {
        // Broken attributes are not result markers.
      }
    }
  }
  return [...links];
}

/** Pirateiro's desktop table holds peer badges beside the title anchor. */
export function pirateiroResultLinks(body: string, siteUrl: string): string[] {
  const links = new Set<string>();
  const origin = new URL(siteUrl).origin;
  for (const row of body.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)) {
    if (!/<h6\b[^>]*\bclass\s*=\s*["'][^"']*\bpt-title\b[^"']*["']/i.test(row[1])) continue;
    for (const anchor of row[1].matchAll(/<a\b[^>]*\bhref\s*=\s*(?:"([^"]*)"|'([^']*)')/gi)) {
      try {
        const url = new URL(anchor[1] || anchor[2], siteUrl);
        if (url.origin === origin && /^\/torrent\/\d+$/.test(url.pathname)) links.add(url.href);
      } catch {
        // Malformed result attributes are not markers.
      }
    }
  }
  return [...links];
}
