# VERSION: 1.03
"""
Sukebei Nyaa adult anime search. Scrapes the HTML results table and follows
the pagination, reading the total count from the "Displaying results 1-N out
of M results" footer line.
"""

from __future__ import annotations

import math
import re
from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


# some other imports if necessary
class nyaa_phuong:
    url = "https://sukebei.nyaa.si"
    name = "Sukebei Nyaa"  # spaces and special characters are allowed here
    # Which search categories are supported by this search engine and their corresponding id
    # Possible categories are ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "6",
        "tv": "4",
        "music": "1",
        "games": "2",
        "anime": "7",
        "software": "3",
    }

    def __init__(self) -> None:
        pass

    class RowParser(HTMLParser):
        """Collects the <tr> rows of the results table.

        Each row is a list of cells; each cell is (text, [hrefs]) so the
        anchor hrefs inside a <td> are preserved (the original bs4 code read
        a.get('href'), not the cell text)."""

        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.rows: list[list[tuple[str, list[str]]]] = []
            self.in_results: bool = False
            self.depth: int = 0
            self.cur: list[tuple[str, list[str]]] | None = None
            self.cell: tuple[str, list[str]] | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if tag == "table":
                self.depth += 1
                if not self.in_results and "results" in (params.get("class") or ""):
                    self.in_results = True
                return
            if not self.in_results:
                return
            if tag == "tr":
                self.cur = []
            elif tag == "td" and self.cur is not None:
                self.cell = ("", [])
            elif tag == "a" and self.cell is not None:
                href = params.get("href")
                if href is not None:
                    self.cell[1].append(href)

        def handle_data(self, data: str) -> None:
            if self.cell is not None:
                self.cell = (self.cell[0] + data, self.cell[1])

        def handle_endtag(self, tag: str) -> None:
            if not self.in_results:
                return
            if tag == "td" and self.cell is not None and self.cur is not None:
                self.cur.append(self.cell)
                self.cell = None
            elif tag == "tr" and self.cur is not None:
                self.rows.append(self.cur)
                self.cur = None
            elif tag == "table":
                self.depth -= 1
                if self.depth <= 0:
                    self.in_results = False

    @staticmethod
    def _cell_text(cell: tuple[str, list[str]]) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cell[0])).strip()

    @staticmethod
    def _first_href(cell: tuple[str, list[str]]) -> str:
        return cell[1][0] if cell[1] else ""

    @staticmethod
    def _last_href(cell: tuple[str, list[str]]) -> str:
        return cell[1][-1] if cell[1] else ""

    @staticmethod
    def _size_bytes(raw: str) -> int:
        m = re.search(r"([\d.]+)\s*([A-Za-z]+)", raw)
        if not m:
            return 0
        value = float(m.group(1))
        unit = m.group(2)
        if unit == "GiB":
            return int(value * 1073741824)
        if unit == "MiB":
            return int(value * 1000000)
        return 0

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = "all") -> None:
        # what is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        # cat is the name of a search category in ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
        # q - query, f - filter, c - category
        base_url = "https://sukebei.nyaa.si/?q=%s&f=0&c=0_0"
        base_url_with_query = base_url % what
        response = retrieve_url(base_url_with_query)
        info = re.search(r"Displaying results 1-(\d+) out of (\d+) results", response)
        item_per_pages = info.group(1) if info else "75"
        total_results = info.group(2) if info else "0"
        number_of_page = (
            math.ceil(float(total_results) / float(item_per_pages)) if item_per_pages != "0" else 1
        )
        for i in range(int(number_of_page)):
            base_url_with_query_and_page = base_url_with_query + f"&p={i + 1!s}"
            response = retrieve_url(base_url_with_query_and_page)
            parser = self.RowParser()
            parser.feed(response)
            parser.close()
            for tds in parser.rows:
                if len(tds) < 7:
                    continue
                ref = self._first_href(tds[1])
                title = self._cell_text(tds[1])
                link = self._last_href(tds[2])
                sizeInBytes = self._size_bytes(self._cell_text(tds[3]))
                seeders = self._cell_text(tds[5])
                leechers = self._cell_text(tds[6])
                try:
                    seeds = int(seeders)
                except ValueError:
                    seeds = -1
                try:
                    leech = int(leechers)
                except ValueError:
                    leech = -1
                res: SearchResults = {
                    "link": link,
                    "name": title,
                    "size": str(sizeInBytes),
                    "seeds": seeds,
                    "leech": leech,
                    "engine_url": self.url,
                    "desc_link": self.url + ref,
                }
                prettyPrinter(res)
