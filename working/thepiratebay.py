# VERSION: 1.1
"""
The Pirate Bay (https://thepiratebay.org) search engine. Uses the
apibay.org JSON API and builds magnets with a fixed list of public trackers.
"""

import json
import urllib.parse
from typing import ClassVar, TypedDict

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class TpbEntry(TypedDict):
    id: int
    name: str
    size: int
    seeders: int
    leechers: int
    info_hash: str


class thepiratebay:
    url = "https://thepiratebay.org/"
    api_url = "https://apibay.org/"
    name = "The Pirate Bay"
    """ 
        TLDR; It is safer to force an 'all' research
        The Pirate Bay categories requires to set GET parameters
    """
    supported_categories: ClassVar[dict[str, str]] = {"all": "0"}

    def parseJSON(self, collection: list[TpbEntry]):
        if collection[0]["name"] == "No results returned":
            return
        for torrent in collection:
            data: SearchResults = {
                "link": "magnet:?xt=urn:btih:{}&dn={}&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A6969%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2710%2Fannounce&tr=udp%3A%2F%2F9.rarbg.me%3A2780%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2730%2Fannounce&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=http%3A%2F%2Fp4p.arenabg.com%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce".format(
                    torrent["info_hash"], urllib.parse.quote(torrent["name"])
                ),
                "name": torrent["name"],
                "size": torrent["size"],
                "seeds": torrent["seeders"],
                "leech": torrent["leechers"],
                "engine_url": self.url,
                "desc_link": "https://thepiratebay.org/description.php?id={}".format(torrent["id"]),
            }
            prettyPrinter(data)

    def search(self, what: str, cat: str = "all"):
        url = f"{self.api_url}q.php?q={what}&cat=0"
        # Getting JSON from API
        collection: list[TpbEntry] = json.loads(retrieve_url(url))
        self.parseJSON(collection)
