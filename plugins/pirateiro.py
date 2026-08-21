# VERSION: 1.3
"""
Pirateiro search. Scrapes the paginated HTML search results (9 pages max);
the listing carries no size and each row's link is its own detail page, whose
magnet is resolved by download_torrent, following the kickasstorrents
download-button chain if needed.
"""

import re
import urllib.parse
from typing import ClassVar

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


# Raised when a torrent page is missing its download link.
class ParseError(Exception):
    pass


class pirateiro:
    url = "https://pirateiro.io/"
    name = "Pirateiro"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "anime": "2",
        "games": "3",
        "movies": "1",
        "music": "4",
        "software": "6",
        "tv": "5",
    }
    max_pages = 10

    class HTMLParser:
        def __init__(self, url: str):
            self.url = url
            self.noTorrents = False

        def feed(self, html: str):
            self.noTorrents = False
            torrents = self.__findTorrents(html)
            resultSize = len(torrents)
            if resultSize == 0:
                self.noTorrents = True
                return
            for torrent in range(resultSize):
                data = SearchResults(
                    link=torrents[torrent][0],
                    name=torrents[torrent][1],
                    size=torrents[torrent][2],
                    seeds=torrents[torrent][3],
                    leech=torrents[torrent][4],
                    engine_url=self.url,
                    desc_link=torrents[torrent][5],
                )
                prettyPrinter(data)

        def __findTorrents(self, html: str):
            torrents: list[tuple[str, str, int, int, int, str]] = []
            links = re.findall(
                r"<a href=\"(.+?)\".+?<h6.+?>(.+?)</h6>.+?(\d+)</span>.+?(\d+)</span>.+?</a>",
                html,
            )
            for a in links:
                # Size is not listed (-1); the row's href doubles as its
                # detail page (link and desc_link are the same).
                torrents.append((a[0], a[1], -1, int(a[2]), int(a[3]), a[0]))
            return torrents

    def download_torrent(self, info: str):
        # The detail page holds the magnet inline, or else a "btn-down"
        # button whose href may point at a kickasstorrents host; that is
        # rewritten to katcr and fetched again recursively.
        torrent_page = retrieve_url(urllib.parse.unquote(info))
        magnet_match = re.search(r"\"(magnet:.*?)\"", torrent_page)
        if magnet_match and magnet_match.groups():
            print(f"{magnet_match.groups()[0]} {info}")
        else:
            dl_link = re.search(
                r"<a class=\"btn-down\".+?href=\"(.+?)\".+>.+?</a>",
                torrent_page.replace("	", "").replace("\n", "").replace("\r", ""),
            )
            if dl_link and dl_link.groups():
                self.download_torrent(dl_link.groups()[0].replace("kickasstorrents", "katcr"))
            else:
                raise ParseError("Error, please fill a bug report!")

    def search(self, what, cat="all"):
        what = what.replace("%20", "+")
        parser = self.HTMLParser(self.url)
        cat_str = "" if cat == "all" else f"&category={self.supported_categories[cat]}"
        for currPage in range(1, self.max_pages):
            url = f"{self.url}search?query={what}&page={currPage}{cat_str}"
            html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
            parser.feed(html)
            if parser.noTorrents:
                break
