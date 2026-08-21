# VERSION: 1.3
"""
Snowfl (https://snowfl.com) search engine. Based on gitDew's work
(https://github.com/gitDew/qbittorrent-snowfl-search-plugin). The site's
anti-bot JS returns a token that has to be scraped before any query is made.
"""

from __future__ import annotations

import json
import random
import re
import string
import time
import urllib.parse
from typing import ClassVar, TypedDict

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


# Raised when a detail page is missing its magnet link.
class ParseError(Exception):
    pass


class Torrent(TypedDict):
    """One element of the JSON response returned for a search query."""

    name: str
    size: str
    seeder: int
    leecher: int
    url: str
    # Present only for entries that expose a magnet link; missing ones fall
    # back to the detail-page link at print time (see `feed`).
    magnet: str


class snowfl:
    url = "https://snowfl.com/"
    name = "Snowfl"
    # No categories provided
    supported_categories: ClassVar[dict[str, str]] = {"all": "0"}

    class Parser:
        def __init__(self, url: str) -> None:
            self.url = url
            self.token = self.__retrieveToken()

        def feed(self, collection: list[Torrent]) -> None:
            for torrent in collection:
                data = SearchResults(
                    link=torrent["magnet"]
                    if "magnet" in torrent
                    else urllib.parse.quote(torrent["url"]),
                    name=torrent["name"],
                    size=str(torrent["size"]),
                    seeds=int(torrent["seeder"]),
                    leech=int(torrent["leecher"]),
                    engine_url=self.url,
                    desc_link=torrent["url"],
                )
                prettyPrinter(data)

        def __retrieveToken(self) -> str:
            index_html = retrieve_url(self.url + "index.html")
            file_name = re.findall(r".+?\"(b.min.js\?.+)\"", index_html)[0]
            script = retrieve_url(self.url + file_name)
            # Retrieving the token
            token = re.findall(r"\"([a-zA-Z0-9]+)\";\$\(\(function\(\){var e,t,n,r,o,a,i=", script)[
                0
            ]
            return token

        def generateQuery(self, what: str) -> str:
            random_str = "".join(
                random.choice(string.ascii_lowercase + string.digits) for _ in range(8)
            )
            return f"{self.url}/{self.token}/{what}/{random_str}/0/SEED/NONE/1?_={int(time.time() * 1000)!s}"

    def download_torrent(self, info: str) -> None:
        if "magnet:?" in info:
            print(f"{info} {info}")
        else:
            torrent_page = retrieve_url(urllib.parse.unquote(info))
            magnet_match = re.search(r"\"(magnet:.*?)\"", torrent_page)
            if magnet_match and magnet_match.groups():
                print(f"{magnet_match.groups()[0]} {info}")
            else:
                raise ParseError("Error, please fill a bug report!")

    def search(self, what: str, cat: str = "all") -> None:
        parser = self.Parser(self.url)
        what = parser.generateQuery(what)
        parser.feed(json.loads(retrieve_url(what)))
