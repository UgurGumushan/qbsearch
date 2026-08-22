function searchFunctionBody(source: string): string {
  const matches = [...source.matchAll(/^[ \t]+def\s+search\s*\(/gm)];
  const start = matches.at(-1)?.index;
  return start === undefined ? "" : source.slice(start);
}

function unescapePythonLiteral(value: string): string {
  return value.replace(/\\([\\'"nrt])/g, (_match, character: string) => {
    switch (character) {
      case "n":
        return "\n";
      case "r":
        return "\r";
      case "t":
        return "\t";
      default:
        return character;
    }
  });
}

function formattedLiterals(source: string): string[] {
  return [...source.matchAll(/\b(?:f|fr|rf)(["'])([\s\S]*?)\1/gi)].map((match) =>
    unescapePythonLiteral(match[2]),
  );
}

function literalUrls(source: string): string[] {
  return [...source.matchAll(/["'](https?:\/\/[^"'\n]+)["']/g)].map((match) =>
    unescapePythonLiteral(match[1]),
  );
}

function queryExpression(expression: string): boolean {
  return /\b(?:what|query|term|searchTerm|search_term)\b/i.test(expression);
}

function expandExpression(
  expression: string,
  query: string,
  category: string,
  siteUrl: string,
  supportedCategory: string,
): string | null {
  const normalized = expression.trim();
  if (queryExpression(normalized)) {
    return encodeURIComponent(query);
  }
  if (/^(?:cat|category)$/i.test(normalized)) {
    return normalized.toLowerCase() === "category" && category === "all"
      ? ""
      : encodeURIComponent(category);
  }
  if (normalized === "cat_str") {
    return "";
  }
  if (/supported_categories/i.test(normalized)) {
    return supportedCategory;
  }
  if (/\b(?:page|page_num|page_number|currPage)\b/i.test(normalized)) {
    return "1";
  }
  if (/\b(?:counter|offset|torrent_count)\b/i.test(normalized)) {
    return "0";
  }
  if (/^(?:self\.)?(?:url|real_url)$/i.test(normalized)) {
    return siteUrl;
  }
  return null;
}

function expandTemplate(
  value: string,
  query: string,
  category: string,
  siteUrl: string,
  supportedCategory: string,
): string | null {
  const unresolvedMarker = "\u0000";
  const expanded = value.replace(/\{([^{}]+)\}/g, (_match, expression: string) => {
    const replacement = expandExpression(
      expression.split(/[!:,]/, 1)[0],
      query,
      category,
      siteUrl,
      supportedCategory,
    );
    if (replacement === null) {
      return unresolvedMarker;
    }
    return replacement;
  });
  if (expanded.includes(unresolvedMarker) || expanded.includes("{")) {
    return null;
  }
  try {
    return new URL(expanded, siteUrl).href;
  } catch {
    return null;
  }
}

function appendQuery(siteUrl: string, prefix: string, query: string): string | null {
  const normalizedPrefix = prefix.replaceAll("/page//", "/page/1/");
  if (normalizedPrefix.includes("https://") && !normalizedPrefix.startsWith("https://")) {
    return null;
  }
  try {
    return new URL(normalizedPrefix + encodeURIComponent(query), siteUrl).href;
  } catch {
    return null;
  }
}

export function buildProbeUrls(
  source: string,
  siteUrl: string,
  query: string,
  category: string,
): string[] {
  const body = searchFunctionBody(source);
  const supportedCategory =
    /supported_categories[\s\S]{0,500}?["']all["'][ \t]*:[ \t]*["']([^"']+)["']/i.exec(
      source,
    )?.[1] ?? "0";
  const candidates: string[] = [];
  const add = (candidate: string | null): void => {
    if (candidate && !candidates.includes(candidate)) {
      candidates.push(candidate);
    }
  };

  const rutorPattern = /PATTERNS\s*=\s*\(\s*["']%ssearch\/%i\/%i\/[^"']*%s["']/i.exec(source);
  if (rutorPattern) {
    try {
      add(new URL(`search/0/0/000/0/${encodeURIComponent(query)}`, siteUrl).href);
    } catch {
      // Keep the ordinary source probes as a fallback for modified variants.
    }
  }

  // Evaluate direct URL + query concatenations before bare URL literals. A
  // source often contains the class URL and the actual search URL together.
  for (const match of body.matchAll(
    /["'](https?:\/\/[^"'\n]*)["'][ \t]*\+[ \t]*(?:str\([^)]*\)[ \t]*\+[ \t]*)?(?:what|query|term|searchTerm|search_term)\b/gi,
  )) {
    add(appendQuery(siteUrl, match[1], query));
  }

  for (const match of body.matchAll(
    /["']([^"'\n]*?(?:search|query|term|page)[^"'\n]*)["'][ \t]*\+[ \t]*(?:what|query|term|searchTerm|search_term)\b/gi,
  )) {
    add(appendQuery(siteUrl, match[1], query));
  }

  const hasFormattedSearchTemplate = formattedLiterals(source).some(
    (value) => queryExpression(value) && /[?&/]/.test(value),
  );
  if (!hasFormattedSearchTemplate) {
    for (const match of source.matchAll(
      /(?:(?:self\.)?(?:url|real_url)|["']https?:\/\/[^"'\n]+["'])[\s\S]{0,220}?["']([^"'\n]*)["'][ \t]*\+[ \t]*(?:what|query|term|searchTerm|search_term)\b/gi,
    )) {
      const segment = match[0];
      const literals = [...segment.matchAll(/["']([^"'\n]*)["']/g)].map((literal) => literal[1]);
      add(appendQuery(siteUrl, literals.join(""), query));
    }
  }

  // JSON API plugins commonly build a dictionary and pass it to urlencode.
  // The query key is enough for a safe one-page smoke probe.
  for (const match of body.matchAll(
    /["'](https?:\/\/[^"'\n]*\?)["'][ \t]*\+[ \t]*urlencode\(\s*query\b/gi,
  )) {
    add(`${match[1]}query=${encodeURIComponent(query)}&offset=0&limit=50`);
  }

  if (queryExpression(body)) {
    for (const literal of literalUrls(body)) {
      if (/[?&]$/.test(literal)) {
        add(`${literal}search=${encodeURIComponent(query)}`);
      }
    }
  }

  const fallbackUrls = [...source.matchAll(/\breturn\s+["'](https?:\/\/[^"'\n]+)["']/gi)]
    .map((match) => match[1])
    .filter((candidate) => !/github\.com/i.test(candidate));
  if (source.includes("real_url")) {
    for (const candidate of fallbackUrls) {
      add(candidate);
    }
  }

  const templates = [...formattedLiterals(source), ...literalUrls(body)].filter(
    (value) =>
      /\{|\b(?:api|page|search|feed|query)\b/i.test(value) &&
      (/https?:\/\//i.test(value) || /\b(?:self\.)?(?:url|real_url)\b/i.test(value)),
  );
  for (const template of templates) {
    add(expandTemplate(template, query, category, siteUrl, supportedCategory));
  }

  // Some engines keep a short relative endpoint next to a later POST/GET
  // call, so there is no query expression on the same line.
  if (queryExpression(body)) {
    for (const match of body.matchAll(
      /(?:self\.)?(?:url|real_url)[ \t]*\+[ \t]*["']([^"'\n]+)["']/gi,
    )) {
      try {
        add(new URL(match[1], siteUrl).href);
      } catch {
        // Ignore malformed source literals and keep looking for a probe.
      }
    }
  }

  const sourceCandidates = [...formattedLiterals(source), ...literalUrls(source)].filter(
    (value) => {
      if (!/\b(?:api|search|feed|query)\b/i.test(value)) {
        return false;
      }
      return !/github\.com\/[^/]+\/[^/]+(?:\/blob\/|\/tree\/)/i.test(value);
    },
  );
  for (const candidate of sourceCandidates) {
    add(expandTemplate(candidate, query, category, siteUrl, supportedCategory));
  }

  return candidates;
}

export function versionFromSource(source: string): string | null {
  return /^\s*#\s*VERSION:\s*(\d+\.\d+)\s*$/im.exec(source)?.[1] ?? null;
}

export function buildProbeUrl(
  source: string,
  siteUrl: string,
  query: string,
  category: string,
): string {
  return buildProbeUrls(source, siteUrl, query, category)[0] ?? siteUrl;
}
