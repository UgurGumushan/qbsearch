# VERSION: 1.00


import json
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter


class animetosho:
    url = "https://animetosho.org"
    name = "Anime Tosho"
    supported_categories: ClassVar[dict[str, str]]  = {
        "all": "all",
        "anime": "anime",
    }

    def __init__(self):
        pass

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat='all'):
        url = f"https://feed.animetosho.org/json?q={what}"
        link = json.loads(retrieve_url(url))

        for result in link:
            current_result = {"engine_url": "https://animetosho.org/"}
            current_result["link"] = result["magnet_uri"]
            current_result["name"] = result["title"]
            current_result["size"] = str(result["total_size"]) + " B"
            current_result["seeds"] = result["seeders"]
            current_result["leech"] = result["leechers"]
            current_result["desc_link"] = result["link"]

            prettyPrinter(current_result)


if __name__ == "__main__":
    a = animetosho()
    a.search("zom+judas")