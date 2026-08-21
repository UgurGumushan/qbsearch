# VERSION: 2.0
"""bt4gprx engine: movies, TV, music, books and software torrents.

Download links are redirects through a third-party domain, so the engine
follows each one and rebuilds a magnet from the torrent hash plus a public
tracker list.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class bt4gprx:
    url = "https://bt4gprx.com/"
    name = "bt4gprx"
    supported_categories: ClassVar[dict[str, str]]  = {'all': '', 'movies': 'movie/', 'tv': 'movie/', 'music': 'audio/', 'books': 'doc/', 'software': 'app/'}

    def __init__(self):
        self.trackerlist: list[str] = []

    class MyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.is_in_container = False
            self.is_in_entry = False
            self.b_value = ""
            self.container_row_count = 0
            self.temp_result: dict[str, str] = {}
            self.results: list[dict[str, str]] = []

        def parse(self, feed: str) -> list[dict[str, str]]:
            super().feed(feed)
            return self.results

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            attr_dict = {key: value for key, value in attrs if value is not None}
            if tag == "div":
                if not self.is_in_container and attr_dict.get("class", "") == "container":
                    self.is_in_container = True
            elif tag == "a":
                if self.is_in_container and all(x in attr_dict for x in ["title", "href"]):
                    self.is_in_entry = True
                    self.temp_result.update(attr_dict)
            elif tag == "b" and self.is_in_entry:
                classname = attr_dict.get("class") or ""
                idname = attr_dict.get("id") or ""
                self.b_value = "filesize" if "cpill" in classname else idname

        def handle_endtag(self, tag: str) -> None:
            if tag == "div":
                self.is_in_entry = False

        def handle_data(self, data: str) -> None:
            if self.b_value != "":
                self.temp_result[self.b_value] = data
                if self.b_value == "leechers":
                    self.results.append(self.temp_result)
                    self.temp_result = {}
                self.b_value = ""

    def search(self, term: str, cat: str = "all") -> None:
        pagenumber = 1
        all_results: list[dict[str, str]] = []
        while True:
            result_page = self.search_page(term, pagenumber, cat)
            if result_page:
                all_results.extend(result_page)
            else:
                break
            pagenumber = pagenumber + 1
        self.pretty_print_results(all_results)

    def search_page(self, term: str, pagenumber: int, cat: str) -> list[dict[str, str]]:
        try:
            query = f"{self.url}{self.supported_categories[cat]}search/{term}/byseeders/{pagenumber}"
            parser = self.MyHTMLParser()
            return parser.parse(retrieve_url(query))
        except Exception:
            return []

    def download_torrent(self, info: str) -> str | None:
        try:
            content = retrieve_url(info)
            match = re.search(r'href="//(downloadtorrentfile.com/hash/[^"]+)', content)
            if not match:
                print("Failed to find downloadtorrentfile.com link.")
                return
            actual_link = "https:" + match.group(0)
        except Exception as e:
            print(f"Error extracting downloadtorrentfile.com link: {e}")
            return
        try:
            hash_value = actual_link.split("/hash/")[1].split("?")[0]
            name_value = actual_link.split("?name=")[1]
        except Exception as e:
            print(f"Error extracting hash and name: {e}")
            return
        if not self.trackerlist:
            self.trackerlist = json.loads(retrieve_url("https://downloadtorrentfile.com/trackerlist"))
        magnet = f"magnet:?xt=urn:btih:{hash_value}&dn={name_value}&tr=" + "&tr=".join(self.trackerlist)
        return magnet

    def pretty_print_results(self, results: list[dict[str, str]]) -> None:
        sorted_results = sorted(results, key=lambda x: int(x['seeders']), reverse=True)
        for result in sorted_results:
            magnet_link = self.download_torrent(urljoin(self.url, result['href']))
            temp_result: SearchResults = {
                'name': result['title'],
                'size': result['filesize'],
                'seeds': int(result['seeders']),
                'leech': int(result['leechers']),
                'engine_url': self.url,
                'link': magnet_link or '',
            }
            prettyPrinter(temp_result)
