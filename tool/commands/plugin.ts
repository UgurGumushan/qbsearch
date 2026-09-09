import { generatePluginCatalog } from "../catalog/command";
import { hardenPlugins } from "../harden/command";

/** Validate standalone plugins without editing (catalog + preamble audit). */
export async function validatePlugins(): Promise<number> {
  const catalogExit = await generatePluginCatalog(["--check"]);
  if (catalogExit !== 0) {
    return catalogExit;
  }
  return hardenPlugins(["--check"]);
}

const JSON_TEMPLATE = (id: string, site: string) => `# VERSION: 1.00
"""Search engine template for ${id}.

Replace the placeholder request and parsing logic with this site's real API contract.
"""

from __future__ import annotations

import json
from typing import ClassVar
from urllib.parse import quote_plus

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

# Safety preamble is inserted at the anchor below by bun run gen.
# QBSEARCH-PREAMBLE-ANCHOR


class ${id}:
    url = "${site}"
    name = "${id}"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    def search(self, what: str, cat: str = "all") -> None:
        _ = cat
        try:
            response = _qbt_helper_retrieve_url(f"{self.url.rstrip('/')}/search/{quote_plus(what)}")
            payload = json.loads(response)
            results = payload.get("results", []) if isinstance(payload, dict) else payload
            if not isinstance(results, list):
                return

            for item in results:
                if not isinstance(item, dict):
                    continue
                link = item.get("link")
                if not isinstance(link, str):
                    continue
                name = str(item.get("name", what))
                size = str(item.get("size", "N/A"))
                seeds = int(item.get("seeds", 0)) if isinstance(item.get("seeds", 0), (int, float, str)) else 0
                leech = int(item.get("leech", 0)) if isinstance(item.get("leech", 0), (int, float, str)) else 0
                prettyPrinter(
                    {
                        "link": link,
                        "name": name,
                        "size": size,
                        "seeds": seeds,
                        "leech": leech,
                        "engine_url": self.url,
                    }
                )
        except Exception:
            return
`;

const HTML_TEMPLATE = (id: string, site: string) => `# VERSION: 1.00
"""Search engine template for ${id}.

Replace this implementation with this site's real HTML scraping logic.
"""

from __future__ import annotations

import re
from typing import ClassVar
from urllib.parse import quote_plus

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

# Safety preamble is inserted at the anchor below by bun run gen.
# QBSEARCH-PREAMBLE-ANCHOR


class ${id}:
    url = "${site}"
    name = "${id}"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    def search(self, what: str, cat: str = "all") -> None:
        _ = cat
        try:
            response = _qbt_helper_retrieve_url(f"{self.url.rstrip('/')}/search/{quote_plus(what)}")
            if not response:
                return
            for match in re.findall(r'<a\\s+href="([^"]+)">([^<]+)</a>', response):
                link, title = match
                if not link.startswith("magnet:") and "http" not in link:
                    continue
                prettyPrinter(
                    {
                        "link": link,
                        "name": title.strip() or what,
                        "size": "N/A",
                        "seeds": 0,
                        "leech": 0,
                        "engine_url": self.url,
                    }
                )
        except Exception:
            return
`;

const TEMPLATES: Record<string, (id: string, site: string) => string> = {
  json: JSON_TEMPLATE,
  html: HTML_TEMPLATE,
};

const KIND_DEFAULT = "json";

function pluginTemplate(kind: string, id: string, site: string): string {
  if (!Object.hasOwn(TEMPLATES, kind)) {
    throw new Error(`unrecognized --kind: ${kind}`);
  }
  return TEMPLATES[kind](id, site);
}

/** plugin --validate audits; --new scaffolds a slim engine (preamble added by gen). */
export async function runPluginCommand(rawArgs: string[]): Promise<number> {
  if (rawArgs.includes("--help") || rawArgs.includes("-h") || rawArgs.length === 0) {
    console.log(`Usage: bun run plugin -- [--validate|--new <id> --kind json|html]

  --validate            Audit catalog parity + safety preambles (no edits)
  --new <id>            Scaffold plugins/<id>.py from the minimal template
    --kind json|html    Template flavor (default: json)
    --site URL          Override the default site URL
`);
    return 0;
  }

  if (rawArgs.includes("--validate")) {
    return validatePlugins();
  }

  const newIndex = rawArgs.indexOf("--new");
  if (newIndex >= 0) {
    const id = rawArgs[newIndex + 1];
    if (!id || !/^[a-z0-9_]+$/.test(id)) {
      console.error("provide a plugin id: --new <plugin-id> (lowercase letters, digits, _)");
      return 2;
    }

    const kindIndex = rawArgs.indexOf("--kind");
    const kind = kindIndex >= 0 ? (rawArgs[kindIndex + 1] ?? KIND_DEFAULT) : KIND_DEFAULT;
    if (!(kind in TEMPLATES)) {
      console.error(`unrecognized --kind: ${kind}`);
      return 2;
    }

    const siteIndex = rawArgs.indexOf("--site");
    const site = (siteIndex >= 0 ? (rawArgs[siteIndex + 1] ?? "") : "https://example.com").trim();
    if (!site) {
      console.error("--site requires a URL value");
      return 2;
    }

    const path = `plugins/${id}.py`;
    if (await Bun.file(path).exists()) {
      console.error(`${path} already exists`);
      return 1;
    }

    await Bun.write(path, pluginTemplate(kind, id, site));
    console.log(`Created ${path} (${kind} template). Next: bun run gen -- --write --only harden`);
    return 0;
  }

  console.error(`unrecognized plugin arguments: ${rawArgs.join(" ")}`);
  return 2;
}
