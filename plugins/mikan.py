# VERSION: 0.4
"""
MikanProject anime search. Queries the site's RSS search endpoint (one page of
results) and maps each item's enclosure to its .torrent link.
"""

import urllib.request
from typing import ClassVar
from xml.etree import ElementTree

from helpers import _headers as headers
from novaprinter import SearchResults, prettyPrinter


class EngineQueryError(Exception):
    pass


class mikan:
    name = "MikanProject"
    url = "https://mikanime.tv"

    supported_categories: ClassVar[dict[str, str]] = {"all": "", "anime": ""}

    @classmethod
    def __print_message(cls, msg: str) -> None:
        prettyPrinter(
            SearchResults(
                engine_url=cls.url,
                seeds=-1,
                leech=-1,
                size=0,
                name=msg,
                link="no link",
                desc_link=cls.url,
            )
        )

    @classmethod
    def __request(cls, target: str) -> str:
        req = urllib.request.Request(f"{cls.url}/RSS/Search?searchstr={target}", headers=headers)
        res = urllib.request.urlopen(req)
        if res.status != 200:
            raise EngineQueryError(f"http status code {res.status}")
        return res.read().decode("utf-8")

    @classmethod
    def __parse(cls, text: str) -> None:
        try:
            search_result = ElementTree.fromstring(text)
            channel = search_result.find("channel")
            if channel is None:
                raise EngineQueryError("parse error")
            for item in channel.findall("item"):
                title = item.findtext("title")
                enclosure = item.find("enclosure")
                if enclosure is None:
                    raise EngineQueryError("parse error")
                row = SearchResults(
                    engine_url=cls.url,
                    seeds=-1,
                    leech=-1,
                    name=title if title is not None else "",
                    link=enclosure.attrib["url"],
                    size=enclosure.attrib["length"],
                    desc_link=item.findtext("link") or "",
                )
                prettyPrinter(row)
        except (ElementTree.ParseError, AttributeError, KeyError):
            raise EngineQueryError("parse error")

    def search(self, what: str, cat: str = "all") -> None:
        try:
            self.__parse(self.__request(what))
        except Exception as e:
            self.__print_message("error: " + str(e))
