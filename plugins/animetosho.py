# VERSION: 1.00
"""Anime Tosho engine: general anime torrent search.

Results come from the site's JSON feed API as magnet links, so no HTML
parsing is needed.
"""

import json
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class animetosho:
    url = "https://animetosho.org"
    name = "Anime Tosho"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "all",
        "anime": "anime",
    }

    def __init__(self) -> None:
        pass

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def search(self, what: str, cat: str = "all") -> None:
        url = f"https://feed.animetosho.org/json?q={what}"
        link = json.loads(retrieve_url(url))

        for result in link:
            current_result: SearchResults = {
                "engine_url": "https://animetosho.org/",
                "link": result["magnet_uri"],
                "name": result["title"],
                "size": str(result["total_size"]) + " B",
                "seeds": result["seeders"],
                "leech": result["leechers"],
                "desc_link": result["link"],
            }

            prettyPrinter(current_result)


if __name__ == "__main__":
    a = animetosho()
    a.search("zom+judas")
