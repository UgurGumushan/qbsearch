# VERSION: 1.2
"""
RockBox (rawkbawx.rocks) music search. Scrapes the HTML torrent listing,
reading the magnet link, size, seeders/leeches and date from each row, and
follows the pagination until a page yields no torrents.
"""

from __future__ import annotations

import re
from datetime import datetime
from time import sleep
from typing import ClassVar
from urllib.parse import quote, unquote

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class rockbox:
    url = "https://rawkbawx.rocks/"
    name = "RockBox"
    # Only an "all" category is exposed: RockBox's music categories are too
    # fine-grained for qBittorrent's fixed category set to filter on well.
    supported_categories: ClassVar[dict[str, str]] = {"all": "0"}

    class HTMLParser:
        def __init__(self, url: str) -> None:
            self.url = url
            self.noTorrents = False

        def feed(self, html: str) -> None:
            self.noTorrents = False
            torrents = self.__findTorrents(html)
            if len(torrents) == 0:
                self.noTorrents = True
                return
            for torrent in range(len(torrents)):
                data = SearchResults(
                    link=torrents[torrent][0],
                    name=torrents[torrent][1],
                    size=torrents[torrent][2],
                    seeds=int(torrents[torrent][3]),
                    leech=int(torrents[torrent][4]),
                    engine_url=self.url,
                    desc_link=torrents[torrent][5],
                    pub_date=torrents[torrent][6],
                )
                prettyPrinter(data)

        def __findTorrents(self, html: str) -> list[tuple[str, str, str, str, str, str, int]]:
            torrents: list[tuple[str, str, str, str, str, str, int]] = []
            # The site renders its rows with uppercase TR tags
            trs = re.findall(r"<TR>\s<td align=\"center\".*?</TR>", html)
            for tr in trs:
                # Extract from the A node all the needed information
                url_titles = re.search(
                    r"HREF=\"(details.+?)\".+?details\:\s?(.+?)\">.+?HREF=(download.+?)>.+?lista\">(.+?)</td>.+?([0-9\,\.]+ (TB|GB|MB|KB)).+?peers details\">([0-9,]+).+?peers details\">([0-9,]+)",
                    tr,
                )
                if url_titles:
                    timestamp = int(datetime.strptime(url_titles.group(4), "%d/%m/%Y").timestamp())
                    torrents.append(
                        (
                            quote(f"{self.url}{url_titles.group(3)}"),
                            url_titles.group(2),
                            url_titles.group(5),
                            url_titles.group(7),
                            url_titles.group(8),
                            f"{self.url}{url_titles.group(1)}",
                            timestamp,
                        )
                    )
            return torrents

    def download_torrent(self, download_url: str) -> None:
        unquoted_magnet = unquote(download_url)
        print(unquoted_magnet + " " + unquoted_magnet)

    def search(self, what: str, cat: str = "all") -> None:
        what = what.replace("%20", "+")
        parser = self.HTMLParser(self.url)
        counter: int = 0
        while True:
            url = (
                f"{self.url}torrents.php?active=0&search={what}&options=0&order=data&page={counter}"
            )
            html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
            parser.feed(html)
            if parser.noTorrents:
                break
            counter += 1
            sleep(3)
