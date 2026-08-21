# VERSION: 1.0


from __future__ import annotations

import json
from datetime import datetime
from typing import ClassVar
from urllib.parse import urlencode

from helpers import retrieve_url
from novaprinter import prettyPrinter


class cloudtorrents:
    url = "https://cloudtorrents.com"
    name = "CloudTorrents"
    supported_categories: ClassVar[dict[str, object | str]]  = {
        "all": None,
        "anime": "1",
        "software": "2",
        "books": "3",
        "games": "4",
        "movies": "5",
        "music": "6",
        "tv": "8",
    }

    def quote_via(self, string, safe="/", encoding=None, errors=None):
        return str(string, "utf-8") if isinstance(string, bytes) else string

    def search(self, what, cat="all"):
        query = {
            "offset": 0,
            "limit": 50,
            "query": what,
        }
        if cat != "all" and cat in self.supported_categories:
            query["torrent_type"] = self.supported_categories[cat]
        items = []
        while True:
            url = "https://api.cloudtorrents.com/search/?" \
                + urlencode(query, quote_via=self.quote_via)
            encoded = retrieve_url(url)
            decoded = json.loads(encoded)
            for result in decoded["results"]:
                torrent = result["torrent"]
                desc_link = self.url \
                    + "/" + torrent["torrentType"]["name"].lower() \
                    + "/" + str(result["id"])
                pub_date = int(datetime.fromisoformat(torrent["uploadedAt"]).timestamp())
                item = {
                    "link": torrent["torrentMagnet"],
                    "name": torrent["name"],
                    "size": torrent["size"],
                    "seeds": torrent["seeders"],
                    "leech": torrent["leechers"],
                    "engine_url": self.url,
                    "desc_link": desc_link,
                    "pub_date": pub_date,
                }
                items.append(item)
            if decoded["next"] is None:
                break
            query["offset"] += query["limit"]
        items.sort(reverse=True, key=lambda item: item["seeds"])
        for item in items:
            prettyPrinter(item)