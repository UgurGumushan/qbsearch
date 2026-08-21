# VERSION: 1.1
"""
Torrent Downloads (https://torrentdownloads.pro) search engine. Scrapes
result rows and, for each row, fetches the torrent page to extract the magnet
link (rows without a /torrent/ link, i.e. featured links, are skipped); later
pages are walked concurrently in threads.
"""

from __future__ import annotations

import re
import threading
import time
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class torrentdownloads:
    url = "https://torrentdownloads.pro"
    name = "Torrent Downloads"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "anime": "1",
        "books": "2",
        "games": "3",
        "movies": "4",
        "music": "5",
        "software": "7",
        "tv": "8",
    }

    next_page_regex = r"<a.*?>>><\/a>"
    has_next_page = True

    class MyHtmlParser(HTMLParser):
        def error(self, message):
            pass

        DIV, P, A, SPAN, B = ("div", "p", "a", "span", "b")

        def __init__(self, url: str):
            HTMLParser.__init__(self)
            self.magnet_regex = r'href=["\']magnet:.+?["\']'

            self.url = url
            self.row: dict[str, str | int] = {}
            self.column = 0

            self.foundContainer = False
            self.insideRow = False
            self.insideCell = False
            self.insideNameCell = False

            self.shouldParseName = False
            self.shouldGetCategory = False
            self.shouldGetSize = False
            self.shouldGetSeeds = False
            self.shouldGetLeechs = False

            self.alreadyParseName = False
            self.alreadyParsesLink = False
            self.shouldSkipResult = False

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            cssClasses = params.get("class") or ""

            if "inner_container" in cssClasses:
                self.foundContainer = True

            if "grey_bar3" in cssClasses and tag == self.DIV:
                self.insideRow = True

            if self.insideRow and tag == self.SPAN and not self.shouldSkipResult:
                self.column += 1
                self.insideCell = True

            if self.insideRow and tag == self.P:
                self.insideNameCell = True

            if self.insideCell:
                if self.column == 2:
                    self.shouldGetLeechs = True

                if self.column == 3:
                    self.shouldGetSeeds = True

                if self.column == 4:
                    self.shouldGetSize = True

            if self.insideNameCell and tag == self.A:
                self.shouldParseName = True
                href = params.get("href") or ""
                if href.startswith("/torrent/"):
                    link = f"{self.url}/{href}"
                    self.row["desc_link"] = link

                    torrent_page = retrieve_url(link)
                    matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                    magnet_urls = [x.group() for x in matches]
                    self.row["link"] = magnet_urls[0].split('"')[1]
                else:
                    self.shouldSkipResult = True

            if self.insideNameCell and tag == self.B:
                self.shouldSkipResult = True

        def handle_data(self, data):
            if self.shouldParseName:
                self.row["name"] = data
                self.shouldParseName = False

            if self.shouldGetSize:
                size = data.replace("&nbsp;", "").replace("\xa0", " ")
                self.row["size"] = size
                self.shouldGetSize = False

            if self.shouldGetSeeds:
                self.row["seeds"] = data
                self.shouldGetSeeds = False

            if self.shouldGetLeechs:
                self.row["leech"] = data
                self.shouldGetLeechs = False

        def handle_endtag(self, tag):
            if tag == self.SPAN or tag == self.P:
                self.insideCell = False

            if tag == self.P:
                self.insideNameCell = False

            if tag == self.DIV and self.insideRow:
                self.row["engine_url"] = self.url
                if not self.shouldSkipResult:
                    prettyPrinter(
                        SearchResults(
                            link=str(self.row.get("link", "")),
                            name=str(self.row.get("name", "")),
                            size=str(self.row.get("size", "")),
                            seeds=int(str(self.row.get("seeds", 0)).strip() or 0),
                            leech=int(str(self.row.get("leech", 0)).strip() or 0),
                            engine_url=self.url,
                            desc_link=str(self.row.get("desc_link", "")),
                        )
                    )
                self.column = 0
                self.row = {}
                self.insideRow = False
                self.shouldSkipResult = False

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def getPageUrl(self, what: str, cat: str, page: int) -> str:
        return f"{self.url}/search/?new=1&s_cat={cat}&search={what}&page={page}"

    def threaded_search(self, page: int, what: str, cat: str) -> None:
        parser = self.MyHtmlParser(self.url)
        page_url = self.getPageUrl(what, cat, page)
        retrievedHtml = retrieve_url(page_url)
        next_page_matches = re.finditer(self.next_page_regex, retrievedHtml, re.MULTILINE)
        next_page = [x.group() for x in next_page_matches]
        if len(next_page) == 0:
            self.has_next_page = False
        parser.feed(retrievedHtml)
        parser.close()

    def search(self, what: str, cat: str = "all") -> None:
        page = 1
        search_category = self.supported_categories[cat]
        what = what.replace("%20", "+")
        what = what.replace(" ", "+")

        threads = []
        while self.has_next_page:
            t = threading.Thread(args=(page, what, search_category), target=self.threaded_search)
            t.start()
            time.sleep(0.5)
            threads.append(t)

            page += 1

        for t in threads:
            t.join()
