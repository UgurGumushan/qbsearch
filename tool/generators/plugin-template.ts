import { pythonStringLiteral } from "../core/python-parse";

const HEADER = (id: string, site: string, imports: string) => `# VERSION: 1.00
"""Search engine template for ${id}.

Replace the placeholder request and parsing logic with the site's real contract.
"""

from __future__ import annotations

${imports}
from typing import ClassVar
from urllib.parse import parse_qs, quote_plus${imports.includes("HTMLParser") ? ", urljoin" : ""}, urlsplit

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

# Safety preamble is inserted at the anchor below by bun run gen.
# QBSEARCH-PREAMBLE-ANCHOR


def _usable_link(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme == "magnet":
            return any(
                re.fullmatch(r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", item)
                for item in parse_qs(parsed.query).get("xt", [])
            )
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False


class ${id}:
    url = ${pythonStringLiteral(site)}
    name = "${id}"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}
`;

export function renderPluginTemplate(kind: "json" | "html", id: string, site: string): string {
  if (kind === "json") {
    return `${HEADER(id, site, "import json\nimport re")}
    @staticmethod
    def _peers(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return -1
        try:
            return max(-1, int(value))
        except (ValueError, OverflowError):
            return -1

    def search(self, what: str, cat: str = "all") -> None:
        _ = cat
        _ = _qbt_new_deadline()
        response = retrieve_url(f"{self.url.rstrip('/')}/search/{quote_plus(what)}")
        try:
            payload = json.loads(response)
        except (TypeError, ValueError):
            return
        results = payload.get("results", []) if isinstance(payload, dict) else payload
        if not isinstance(results, list):
            return
        seen: set[str] = set()
        for item in results:
            if len(seen) >= MAX_DETAILS:
                break
            if not isinstance(item, dict):
                continue
            link, title = item.get("link"), item.get("name")
            if not _usable_link(link) or not isinstance(title, str) or not title.strip():
                continue
            if link in seen:
                continue
            seen.add(link)
            size = item.get("size", -1)
            prettyPrinter(
                {
                    "link": link,
                    "name": title.strip(),
                    "size": size if isinstance(size, (str, int)) else -1,
                    "seeds": self._peers(item.get("seeds")),
                    "leech": self._peers(item.get("leech")),
                    "engine_url": self.url,
                }
            )
`;
  }
  return `${HEADER(id, site, "import re\nfrom html.parser import HTMLParser")}
    class ResultParser(HTMLParser):
        def __init__(self, site: str) -> None:
            super().__init__(convert_charrefs=True)
            self.site = site
            self.link = ""
            self.title: list[str] = []
            self.seen: set[str] = set()

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag != "a":
                return
            self.link = ""
            self.title = []
            href = dict(attrs).get("href")
            if not href:
                return
            try:
                link = urljoin(self.site, href)
                if _usable_link(link) and (
                    link.startswith("magnet:") or urlsplit(link).path.lower().endswith(".torrent")
                ):
                    self.link = link
            except ValueError:
                return

        def handle_data(self, data: str) -> None:
            if self.link:
                self.title.append(data)

        def handle_endtag(self, tag: str) -> None:
            if tag != "a":
                return
            title = "".join(self.title).strip()
            if self.link and title and self.link not in self.seen and len(self.seen) < MAX_DETAILS:
                self.seen.add(self.link)
                prettyPrinter(
                    {
                        "link": self.link,
                        "name": title,
                        "size": -1,
                        "seeds": -1,
                        "leech": -1,
                        "engine_url": self.site,
                    }
                )
            self.link = ""
            self.title = []

    def search(self, what: str, cat: str = "all") -> None:
        _ = cat
        _ = _qbt_new_deadline()
        response = retrieve_url(f"{self.url.rstrip('/')}/search/{quote_plus(what)}")
        parser = self.ResultParser(self.url)
        parser.feed(response)
        parser.close()
`;
}
