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
