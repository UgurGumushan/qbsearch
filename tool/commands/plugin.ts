import { generatePluginCatalog } from "../../generate/catalog/command";
import { hardenPlugins } from "../../generate/harden/command";

/** Validate standalone plugins without editing (catalog + preamble audit). */
export async function validatePlugins(): Promise<number> {
  const catalogExit = await generatePluginCatalog(["--check"]);
  if (catalogExit !== 0) {
    return catalogExit;
  }
  return hardenPlugins(["--check"]);
}

const JSON_TEMPLATE = (id: string, site: string) => `# VERSION: 1.00
"""TODO: describe the ${id} engine."""

from __future__ import annotations

from typing import ClassVar

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

# Safety preamble is inserted at the anchor below by bun run gen.
# QBSEARCH-PREAMBLE-ANCHOR


class ${id}:
    url = "${site}"
    name = "${id}"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    def search(self, what: str, cat: str = "all") -> None:
        try:
            response = _qbt_helper_retrieve_url(self.url + str(what))
            _qbt_prettyPrinter(
                {
                    "link": response,
                    "name": what,
                    "size": "1 MB",
                    "seeds": 1,
                    "leech": 0,
                    "engine_url": self.url,
                }
            )
        except Exception:
            return
`;

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
    const kind = kindIndex >= 0 ? (rawArgs[kindIndex + 1] ?? "json") : "json";
    if (kind !== "json" && kind !== "html") {
      console.error(`unrecognized --kind: ${kind}`);
      return 2;
    }
    const siteIndex = rawArgs.indexOf("--site");
    const site = siteIndex >= 0 ? (rawArgs[siteIndex + 1] ?? "") : "https://example.com";
    if (!site) {
      console.error("--site requires a URL value");
      return 2;
    }
    const path = `plugins/${id}.py`;
    if (await Bun.file(path).exists()) {
      console.error(`${path} already exists`);
      return 1;
    }
    await Bun.write(path, JSON_TEMPLATE(id, site));
    console.log(`Created ${path} (${kind} template). Next: bun run gen -- --write --only harden`);
    return 0;
  }
  console.error(`unrecognized plugin arguments: ${rawArgs.join(" ")}`);
  return 2;
}
