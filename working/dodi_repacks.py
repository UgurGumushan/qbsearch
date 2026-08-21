# VERSION: 1.1
"""DODI Repacks engine: PC game repacks.

Does not scrape the site at all: it reads a third-party JSON index of the
repacks and filters it locally against the search terms.
"""

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, ClassVar
from urllib.parse import unquote

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class dodi_repacks:
    url = "https://dodi-repacks.site/"
    name = "DODI Repacks"
    supported_categories: ClassVar[dict[str, str]] = {"all": ""}

    def search(self, what: str, cat: str = "all") -> None:
        search_url = "https://hydralinks.cloud/sources/dodi.json"

        response = retrieve_url(search_url)
        response_json = json.loads(response)

        what = unquote(what)
        search_terms = what.lower().split()

        for result in response_json["downloads"]:
            if any(term in result["title"].lower() for term in search_terms):
                timestamp = int(
                    datetime.strptime(result["uploadDate"], "%Y-%m-%dT%H:%M:%S.%fZ")
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
                res = SearchResults(
                    link=self.download_link(result),
                    name=str(result["title"]),
                    size=result["fileSize"],
                    seeds=-1,
                    leech=-1,
                    engine_url=self.url,
                    desc_link="-1",
                    pub_date=timestamp,
                )
                prettyPrinter(res)

    def download_link(self, result: Mapping[str, Any]) -> str:
        return str(result["uris"][0])
