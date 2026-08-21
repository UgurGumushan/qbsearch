# VERSION: 1.01
"""
MejorTorrent (Spanish) movies and series search. Scrapes the paginated search
results, then fetches each item page: films link their .torrent file directly,
series link their season page. Downloads are password-protected, the key
shown per episode.
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter

MAX_PAGES = 10


class mejortorrent:
    url = "https://www36.mejortorrent.eu"
    name = "MejorTorrent"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "pelicula",
        "tv": "serie",
    }

    class SeriesHtmlParser(HTMLParser):
        def __init__(self, domain: str) -> None:
            HTMLParser.__init__(self)
            self.domain = domain
            self.path = ""
            self.title = ""
            self.title_found = False
            self.table_found = False
            self.item_found = False
            self.field_found = False
            self.key_found = False
            self.column_number = 0
            self.episode: str | None = None
            self.date: int | None = None
            self.key: str | None = None
            self.link: str | None = None

        def init(self, link: str) -> None:
            self.path = link
            self.title = ""
            self.title_found = False
            self.table_found = False
            self.item_found = False
            self.field_found = False
            self.key_found = False
            self.column_number = 0
            self.episode = None
            self.date = None
            self.key = None
            self.link = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if tag == "p":
                if "class" in params and "text-blue-900" in (params["class"] or ""):
                    self.title_found = True
                elif self.field_found:
                    self.key_found = True
            if self.table_found:
                if tag == "tr":
                    self.item_found = True
                elif tag == "td":
                    self.field_found = True
                elif tag == "a" and self.field_found and "href" in params:
                    self.link = params["href"]
            else:
                if tag == "tbody":
                    self.table_found = True

        def handle_data(self, data: str) -> None:
            data = data.strip()
            if self.title_found:
                self.title = data
            if self.field_found:
                if self.column_number == 1:
                    self.episode = data
                elif self.column_number == 2:
                    self.date = round(datetime.timestamp(datetime.strptime(data, "%Y-%m-%d")))
                elif self.column_number == 3 and self.key_found:
                    self.key = data

        def handle_endtag(self, tag: str) -> None:
            if tag == "p":
                if self.title_found:
                    self.title_found = False
                elif self.key_found:
                    self.key_found = False
            if tag == "td" and self.field_found:
                self.field_found = False
                self.column_number += 1
            if tag == "tr" and self.item_found:
                # "Sin clave" ("no key") means the episode has no password
                episode = self.episode if self.episode is not None else ""
                link = self.link if self.link is not None else ""
                key = (
                    ", password: " + self.key
                    if self.key is not None and self.key != "Sin clave"
                    else ""
                )
                prettyPrinter(
                    SearchResults(
                        name=f"{self.title} ({episode}){key}",
                        size=-1,
                        link=f"{self.domain}{link}",
                        desc_link=self.path,
                        engine_url=self.domain,
                        seeds=-1,
                        leech=-1,
                        pub_date=self.date if self.date is not None else 0,
                    )
                )
                self.item_found = False
                self.episode = None
                self.date = None
                self.key = None
                self.link = None
                self.column_number = 0

    def __init__(self) -> None:
        self.tv_parser = self.SeriesHtmlParser(self.url)

    def download_torrent(self, info: SearchResults) -> None:
        print(download_file(info["link"]))

    def search(self, what: str, cat: str = "all") -> None:
        # Search example: https://www21.mejortorrent.zip/busqueda?q=godzilla
        search_url = f"{self.url}/busqueda?q={what}"
        html = retrieve_url(search_url)
        items: list[str] = []
        items.extend(self.parse_page(html, cat))
        for p in range(2, self.get_num_pages(html) + 1):
            if p > MAX_PAGES:
                break
            # Search page example: https://www21.mejortorrent.zip/busqueda/page/3?q=paco
            search_url = f"{self.url}/busqueda/page/{p}?q={what}"
            html = retrieve_url(search_url)
            items.extend(self.parse_page(html, cat))

        for i in items:
            if self.supported_categories["movies"] in i:
                self.parse_film(i)
            elif self.supported_categories["tv"] in i:
                self.parse_tv_season(i)

    def get_num_pages(self, html: str) -> int:
        pages = re.findall(r'"go to page [0-9]+"', html)
        if not pages:
            return 1
        else:
            # map to array of integers and calculate max value
            return max([int(n.strip('"').split(" ")[-1]) for n in pages])

    def parse_page(self, html: str, category: str) -> list[str]:
        # copy minus the "all" entry (its value is the cat filter, not a slug)
        all_categories = {k: v for k, v in self.supported_categories.items() if k != "all"}
        category_patterns = (f'{self.url}/{e}/[0-9]+/[^"]+' for e in list(all_categories.values()))
        pattern = (
            r"({})".format("|".join(category_patterns))
            if category == "all"
            else rf"{self.url}/{self.supported_categories[category]}/[0-9]+/[^\"]+"
        )
        return re.findall(pattern, html)

    def parse_film(self, url: str) -> None:
        html = retrieve_url(url)
        title_match = re.search(r'text-blue-900">[^\<]+', html)
        title = title_match.group(0).split(">")[-1] if title_match else ""
        quality_match = re.search(r"/quality/[^\"]+", html)
        quality = quality_match.group(0).split("/")[-1] if quality_match else ""
        path_match = re.search(r"/torrents/.+\.torrent", html)
        date_match = re.search(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", html)
        pub_date = (
            round(datetime.timestamp(datetime.strptime(date_match.group(0), "%d/%m/%Y")))
            if date_match
            else 0
        )
        info: SearchResults = {
            "name": f"{title} ({quality})",
            "size": -1,
            "link": "{domain}{path}".format(
                domain=self.url, path=path_match.group(0) if path_match else ""
            ),
            "desc_link": url,
            "engine_url": self.url,
            "seeds": -1,
            "leech": -1,
            "pub_date": pub_date,
        }
        prettyPrinter(info)

    def parse_tv_season(self, link: str) -> None:
        html = retrieve_url(link)
        self.tv_parser.init(link)
        self.tv_parser.feed(html)
