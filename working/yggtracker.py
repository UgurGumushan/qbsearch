# VERSION: 1.1
"""
YGGtracker: aggregates a list of public Yggdrasil-tracker nodes and scrapes
each node's JSON API for the query (filtered by category), so one search hits
many semi-private YGG trackers at once. The node list is pulled from GitHub.
"""

import json
from typing import ClassVar, TypedDict
from urllib.parse import unquote, urlencode

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class YggTorrentFile(TypedDict):
    url: str
    name: str
    size: int


class YggTorrentScrape(TypedDict):
    seeders: int
    leechers: int


class YggTorrent(TypedDict):
    url: str
    file: YggTorrentFile
    scrape: YggTorrentScrape


class YggTorrentEntry(TypedDict):
    torrent: YggTorrent


class YggTrackerInfo(TypedDict):
    url: str


class YggNodeResponse(TypedDict):
    torrents: list[YggTorrentEntry]
    tracker: YggTrackerInfo


class YggNode(TypedDict):
    url: str
    categories: dict[str, list[str]]


class yggtracker:
    name = "YGGtracker"
    url = "https://github.com/YGGverse/YGGtracker"
    supported_categories: ClassVar[dict[str, list[object]]] = {
        "all": [],
        "anime": [],
        "books": [],
        "games": [],
        "movies": [],
        "music": [],
        "pictures": [],
        "software": [],
        "tv": [],
    }

    def __init__(self):
        pass

    def search(self, what: str, cat: str = "all") -> None:

        # get distributed nodes registry
        nodes = retrieve_url(
            "https://raw.githubusercontent.com/YGGverse/qbittorrent-yggtracker-search-plugin/main/nodes.json"
        )
        nodes_json: list[YggNode] = json.loads(nodes)

        # check empty response
        if len(nodes_json) == 0:
            return

        # parse results
        for node in nodes_json:
            # apply query request
            what = unquote(what)
            params: dict[str, str] = {"query": what, "filter": "true"}

            # apply categories filter
            categories = list(node["categories"][cat])

            if len(categories) > 0:
                params["categories"] = "|".join(categories)

            # send api request
            response = retrieve_url(node["url"] % urlencode(params))
            response_json: YggNodeResponse = json.loads(response)

            # check empty response
            if len(response_json["torrents"]) == 0:
                continue

            # parse results
            for item in response_json["torrents"]:
                res: SearchResults = {
                    "link": item["torrent"]["file"]["url"],
                    "name": item["torrent"]["file"]["name"],
                    "size": str(item["torrent"]["file"]["size"]) + " B",
                    "seeds": item["torrent"]["scrape"]["seeders"],
                    "leech": item["torrent"]["scrape"]["leechers"],
                    "engine_url": response_json["tracker"]["url"],
                    "desc_link": item["torrent"]["url"],
                }
                prettyPrinter(res)
