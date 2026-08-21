# VERSION: 1.3
"""
YourBittorrent (https://yourbittorrent.com) search engine. Scrapes the
results table; because the site's page navigation is broken, only the first
50 results can be retrieved per query.
"""

import re
import urllib.parse
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


# Raised when a torrent page is missing its .torrent download link.
class ParseError(Exception):
    pass


class yourbittorrent:
    url = "https://yourbittorrent.com/"
    name = "YourBittorrent"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "1",
        "tv": "3",
        "music": "2",
        "games": "4",
        "anime": "6",
        "software": "5",
    }

    # The site's page navigation is broken, so only the first 50 results of a
    # query can be retrieved; the query itself is the only selector.

    class HTMLParser:
        def __init__(self, url: str):
            self.url = url
            self.noTorrents = False

        def feed(self, html: str):
            self.noTorrents = False
            torrents: list[tuple[str, str, str, str, str]] = self.__findTorrents(html)
            resultSize = len(torrents)
            if resultSize == 0:
                self.noTorrents = True
                return
            for torrent in range(resultSize):
                data: SearchResults = {
                    "link": torrents[torrent][0],
                    "name": torrents[torrent][1],
                    "size": torrents[torrent][2],
                    "seeds": int(torrents[torrent][3].replace(",", "")),
                    "leech": int(torrents[torrent][4].replace(",", "")),
                    "engine_url": self.url,
                    "desc_link": urllib.parse.unquote(torrents[torrent][0]),
                }
                prettyPrinter(data)

        def __findTorrents(self, html: str) -> list[tuple[str, str, str, str, str]]:
            torrents: list[tuple[str, str, str, str, str]] = []
            html = re.findall(r"<div class=\"table-responsive\">.+?</table></div>", html)[1]
            trs = re.findall(r"<tr class=\"table-default\">.+?</tr>", html)
            for tr in trs:
                # Extract from the A node all the needed information
                url_titles = re.search(
                    r".+?href=\"(.+?)\".+?title=\"(.+?)\".+?([0-9\.\,]+ (TB|GB|MB|kB)).+?sd\">([0-9,]+)<.+?pr\">([0-9,]+)<",
                    tr,
                )
                if url_titles:
                    torrents.append(
                        (
                            urllib.parse.quote(f"{self.url}{url_titles.group(1)}"),
                            url_titles.group(2)
                            .replace("<b>", "")
                            .replace("</b>", "")
                            .replace("<span style=color:#39a8bb>", "")
                            .replace("</span>", ""),
                            url_titles.group(3).replace(",", ""),
                            url_titles.group(5).replace(",", ""),
                            url_titles.group(6).replace(",", ""),
                        )
                    )
            return torrents

    def download_torrent(self, info: str) -> None:
        torrent_page: str = retrieve_url(urllib.parse.unquote(info))
        file_link = re.search(r"(down/.+?\.torrent)", torrent_page)
        if file_link and file_link.groups():
            print(download_file(self.url + file_link.groups()[0]))
        else:
            raise ParseError("Error, please fill a bug report!")

    def search(self, what: str, cat: str = "all") -> None:
        what = what.replace("%20", "-")
        parser = self.HTMLParser(self.url)
        category = "" if cat == "all" else f"&c={self.supported_categories[cat]}"
        url = f"{self.url}?q={what}{category}"
        # Some replacements to format the html source
        html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
        parser.feed(html)
