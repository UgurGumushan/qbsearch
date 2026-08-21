# VERSION: 1.1
"""
TomaDivx (https://tomadivx.net, Spanish site) search engine. For each result
the engine fetches the detail page to pull out the .torrent link and the size
(labelled 'Tamaño:'); later pages are fetched concurrently in threads.
"""

from __future__ import annotations

import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class tomadivx:
    url = "https://tomadivx.net/"
    headers: dict[str, str] = {  # noqa: RUF012
        "Referer": url
    }
    name = "TomaDivx"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    results_regex = r"<p.+?>Se han encontrado.+?<b>\d+</b>.+?resultados.+?</p>"

    class MyHtmlParser(HTMLParser):
        magnet_regex = r'href=["\'].+?\.torrent["\']'
        size_regex = r"<p.+?><b.+?>Tamaño:</b>.+?</p>"

        def error(self, message: str):
            pass

        DIV, P, A, SPAN = ("div", "p", "a", "span")

        def __init__(self, url: str):
            HTMLParser.__init__(self)

            self.url = url
            self.headers: dict[str, str] = {"Referer": url}
            self.row: dict[str, str] = {}
            self.name = ""
            self.seeds = -1
            self.leech = -1

            self.column = 0

            self.insideBuscadorDiv = False
            self.insideCardDiv = False
            self.insideCardBodyDiv = False
            self.insideResult = False
            self.insideResultSpan = False
            self.insideLink = False
            self.insideType = False
            self.insideBadge = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            cssClasses = params.get("class", "") or ""
            elementId = params.get("id", "")

            if tag == self.DIV and elementId == "buscador":
                self.insideBuscadorDiv = True
                return

            if self.insideBuscadorDiv and "card" in cssClasses and "card-body" not in cssClasses:
                self.insideCardDiv = True
                return

            if self.insideCardDiv and "card-body" in cssClasses:
                self.insideCardBodyDiv = True
                return

            if self.insideCardBodyDiv and tag == self.P and len(cssClasses) == 0:
                self.insideResult = True
                self.name = ""
                return

            if self.insideResult and not self.insideResultSpan and tag == self.SPAN:
                self.insideResultSpan = True
                return

            if self.insideResultSpan and tag == self.A:
                self.insideLink = True
                href = params.get("href")
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                self.row["link"] = link
                torrent_page: str = retrieve_url(link, self.headers)
                matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                magnet_urls = [x.group() for x in matches]
                self.row["link"] = "https:" + magnet_urls[0].split("'")[1]
                matches = re.finditer(self.size_regex, torrent_page, re.MULTILINE)
                size = [x.group() for x in matches]
                sizeEl = re.sub(r"<b.+?>Tamaño:</b>", "", size[0])
                root = ET.fromstring(sizeEl)
                self.row["size"] = (root.text or "").replace(",", ".")
                self.seeds = -1
                self.leech = -1
                return

            if self.insideResultSpan and tag == self.SPAN and len(cssClasses) == 0:
                self.insideType = True
                return

            if self.insideResultSpan and tag == self.SPAN and "badge" in cssClasses:
                self.insideBadge = True
                return

        def handle_data(self, data: str) -> None:
            if self.insideLink:
                self.name = data
                return

            if self.insideType:
                self.name += f" ({data})"
                return

            if self.insideBadge:
                self.name += f" [{data}]"
                return

        def handle_endtag(self, tag: str) -> None:
            if self.insideBadge and tag == self.SPAN:
                self.insideBadge = False
                return

            if self.insideType and tag == self.SPAN:
                self.insideType = False
                return

            if self.insideLink and tag == self.A:
                self.insideLink = False
                return

            if (
                self.insideResultSpan
                and not self.insideBadge
                and not self.insideType
                and tag == self.SPAN
            ):
                self.insideResultSpan = False
                return

            if self.insideResult and tag == self.P:
                res: SearchResults = {
                    "link": self.row["link"],
                    "name": self.name,
                    "size": self.row["size"],
                    "seeds": self.seeds,
                    "leech": self.leech,
                    "engine_url": self.url,
                    "desc_link": self.row["desc_link"],
                }
                prettyPrinter(res)
                self.column = 0
                self.row = {}
                self.name = ""
                self.insideResult = False
                self.insideResultSpan = False
                return

            if self.insideCardBodyDiv and tag == self.DIV:
                self.insideCardBodyDiv = False
                return

            if self.insideCardDiv and self.insideCardBodyDiv is False and tag == self.DIV:
                self.insideCardDiv = False
                return

            if self.insideBuscadorDiv and self.insideCardDiv is False and tag == self.DIV:
                self.insideBuscadorDiv = False
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def get_page_url(self, what: str, page: int) -> str:
        return f"{self.url}/buscar/{what}/page/{page}"

    def threaded_search(self, page: int, what: str) -> None:
        page_url = self.get_page_url(what, page)
        self.headers["Referer"] = page_url
        retrieved_html: str = retrieve_url(page_url, self.headers)
        parser = self.MyHtmlParser(self.url)
        parser.feed(retrieved_html)
        parser.close()

    def search(self, what: str, cat: str = "all") -> None:
        page = 1
        retrieved_html: str = retrieve_url(self.get_page_url(what, page), self.headers)
        matches = re.finditer(self.results_regex, retrieved_html, re.MULTILINE)
        results_el = [x.group() for x in matches]
        root: ET.Element = ET.fromstring(results_el[0])
        results: str = root[0].text or "0"
        pages = math.ceil(int(results) / 10)

        parser = self.MyHtmlParser(self.url)
        parser.feed(retrieved_html)
        parser.close()

        page += 1

        threads: list[threading.Thread] = []
        while page <= pages:
            t = threading.Thread(args=(page, what), target=self.threaded_search)
            t.start()
            time.sleep(0.5)
            threads.append(t)

            page += 1

        for t in threads:
            t.join()
