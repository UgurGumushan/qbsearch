# VERSION: 1.0
"""
Online-Fix game search. Reads the static JSON feed hosted at hydralinks.cloud
(a mirror of online-fix.me) and matches the query terms against every
downloaded game, linking the first URI of each entry.
"""

import json
from collections.abc import Mapping
from typing import Any, ClassVar
from urllib.parse import unquote

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class onlinefix:
    url = "https://online-fix.me/"
    name = "Online-Fix"
    supported_categories: ClassVar[dict[str, str]] = {"all": ""}

    def search(self, what: str, cat: str = "all") -> None:
        search_url = "https://hydralinks.cloud/sources/onlinefix.json"

        response = retrieve_url(search_url)
        response_json = json.loads(response)

        what = unquote(what)
        search_terms = what.lower().split()

        for result in response_json["downloads"]:
            if any(term in result["title"].lower() for term in search_terms):
                res = SearchResults(
                    link=self.download_link(result),
                    name=str(result["title"]),
                    size=result["fileSize"],
                    seeds=-1,
                    leech=-1,
                    engine_url=self.url,
                    desc_link="-1",
                )
                prettyPrinter(res)

    def download_link(self, result: Mapping[str, Any]) -> str:
        return str(result["uris"][0])
