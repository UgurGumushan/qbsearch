# VERSION: 0.4
# AUTHORS: Cycloctane (Cycloctane@octane.top)

import urllib.request
from xml.etree import ElementTree

from helpers import _headers as headers
from novaprinter import prettyPrinter


class mikan:

    name = "MikanProject"
    url = "https://mikanani.me"

    supported_categories = {'all': '', 'anime': ''}

    @classmethod
    def __print_message(cls, msg: str) -> None:
        prettyPrinter({'engine_url': cls.url, 'seeds': -1, 'leech': -1, 'size': 0,
                       'name': msg, 'link': 'no link', 'desc_link': cls.url})

    @classmethod
    def __request(cls, target: str) -> str:
        req = urllib.request.Request(
            f"{cls.url}/RSS/Search?searchstr={target}", headers=headers
        )
        res = urllib.request.urlopen(req)
        if res.status != 200: raise Exception(f"http status code {res.status}")
        return res.read().decode('utf-8')

    @classmethod
    def __parse(cls, text: str) -> None:
        try:
            search_result = ElementTree.fromstring(text)
            for item in search_result.find("channel").findall("item"):
                row = {'engine_url': cls.url, 'seeds': -1, 'leech': -1}
                row['name'] = item.findtext("title")
                row['link'] = item.find("enclosure").attrib['url']
                row['size'] = item.find("enclosure").attrib['length']
                row['desc_link'] = item.findtext('link')
                prettyPrinter(row)
        except (ElementTree.ParseError, AttributeError, KeyError):
            raise Exception("parse error")

    def search(self, what: str, cat: str = 'all') -> None:
        try:
            self.__parse(self.__request(what))
        except Exception as e:
            self.__print_message("error: "+str(e))
