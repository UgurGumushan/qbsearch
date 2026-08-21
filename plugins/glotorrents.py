# VERSION: 1.7
"""
GloTorrents search against the glodls.to mirror. Scrapes the HTML search
results and follows the pagination until a page yields no torrents.
"""

import re
from time import sleep
from typing import ClassVar

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class glotorrents:
    url = "https://glodls.to/"
    name = "GloTorrents"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "1",
        "tv": "41",
        "music": "22",
        "games": "10",
        "anime": "28",
        "software": "18",
        "books": "51",
        "pictures": "70",
    }

    class HTMLParser:
        def __init__(self, url: str) -> None:
            self.url = url
            self.noTorrents = False

        def feed(self, html: str) -> None:
            self.noTorrents = False
            torrents: list[tuple[str, str, str, int, int, str]] = self.__findTorrents(html)
            if len(torrents) == 0:
                self.noTorrents = True
                return
            for link, name, size, seeds, leech, desc_link in torrents:
                prettyPrinter(
                    SearchResults(
                        link=link,
                        name=name,
                        size=size,
                        seeds=seeds,
                        leech=leech,
                        engine_url=self.url,
                        desc_link=desc_link,
                    )
                )

        def __findTorrents(self, html: str) -> list[tuple[str, str, str, int, int, str]]:
            torrents: list[tuple[str, str, str, int, int, str]] = []
            trs = re.findall(r"<tr class=\'t-row\'> <td class=\'ttable_col1\'.+?</tr>", html)
            for tr in trs:
                # One match per result row: title, detail path, magnet link,
                # size, seeders (green cell) and leechers (colored cell).
                url_titles = re.search(
                    r"title=\"(.+?)\".+?href=\"(.+?)\".+?</a>.+?align=\'center\'>.+?href=\"(magnet:.*?)\".+?([0-9\,\.]+ (TB|GB|MB|KB)).+?<font color=\'green\'><b>([0-9,]+)</b>.+?<font color=\'#[0-9a-zA-Z]{6}\'><b>([0-9,]+)</b>",
                    tr,
                )
                if url_titles:
                    torrents.append(
                        (
                            url_titles.group(3),
                            url_titles.group(1),
                            url_titles.group(4).replace(",", ""),
                            int(url_titles.group(6).replace(",", "")),
                            int(url_titles.group(7).replace(",", "")),
                            f"{self.url}{url_titles.group(2)}",
                        )
                    )
            return torrents

    def search(self, what: str, cat: str = "all") -> None:
        what = what.replace("%20", "+")
        parser = self.HTMLParser(self.url)
        counter: int = 0
        while True:
            url = f"{self.url}search_results.php?search={what}&cat={self.supported_categories[cat]}&page={counter}&incldead=0&inclexternal=0"
            html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
            parser.feed(html)
            if parser.noTorrents:
                break
            counter += 1
            sleep(3)
