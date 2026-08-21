# VERSION: 1.1
"""
FitGirl Repacks game search. Reads the static JSON feed hosted at
hydralinks.cloud (a mirror of fitgirl-repacks.site) and matches the query
terms case-insensitively against every downloaded game.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import ClassVar, TypedDict
from urllib.parse import unquote

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class FitGirlDownload(TypedDict):
    title: str
    uploadDate: str
    fileSize: int | float | str
    uris: list[str]


class FitGirlFeed(TypedDict):
    downloads: list[FitGirlDownload]


class fitgirl_repacks:
    url = "https://fitgirl-repacks.site/"
    name = "FitGirl Repacks"
    supported_categories: ClassVar[dict[str, str]] = {"all": ""}

    def search(self, what: str, cat: str = "all") -> None:
        search_url = "https://hydralinks.cloud/sources/fitgirl.json"

        response: str = retrieve_url(search_url)
        feed: FitGirlFeed = json.loads(response)

        what = unquote(what)
        search_terms = what.lower().split()

        for download in feed["downloads"]:
            title = download["title"]
            if not any(term in title.lower() for term in search_terms):
                continue
            timestamp = int(
                datetime.strptime(download["uploadDate"], "%Y-%m-%dT%H:%M:%S.%fZ")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            res: SearchResults = {
                "link": self.download_link(download),
                "name": title,
                "size": download["fileSize"],
                "seeds": -1,
                "leech": -1,
                "engine_url": self.url,
                "desc_link": "-1",
                "pub_date": timestamp,
            }
            prettyPrinter(res)

    def download_link(self, result: FitGirlDownload) -> str:
        return result["uris"][0]
