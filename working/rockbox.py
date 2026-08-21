# VERSION: 1.2

import re
from datetime import datetime
from time import sleep
from typing import ClassVar
from urllib.parse import quote, unquote

from helpers import retrieve_url
from novaprinter import prettyPrinter


class rockbox:
    url = "https://rawkbawx.rocks/"
    name = "RockBox"
    """ 
        TLDR; It is safer to force an 'all' research
        RockBox's categories are very specific for music-type
        qBittorrent does not provide enough categories to implement a good filtering.
    """
    supported_categories: ClassVar[dict[str, str]]  = {"all": "0"}

    class HTMLParser:
        def __init__(self, url):
            self.url = url
            self.noTorrents = False

        def feed(self, html):
            self.noTorrents = False
            torrents = self.__findTorrents(html)
            if len(torrents) == 0:
                self.noTorrents = True
                return
            for torrent in range(len(torrents)):
                data = {
                    "link": torrents[torrent][0],
                    "name": torrents[torrent][1],
                    "size": torrents[torrent][2],
                    "seeds": torrents[torrent][3],
                    "leech": torrents[torrent][4],
                    "engine_url": self.url,
                    "desc_link": torrents[torrent][5],
                    "pub_date": torrents[torrent][6],
                }
                prettyPrinter(data)

        def __findTorrents(self, html):
            torrents = []
            trs = re.findall(r"<TR>\s<td align=\"center\".*?</TR>", html)
            for tr in trs:
                # Extract from the A node all the needed information
                url_titles = re.search(
                    r"HREF=\"(details.+?)\".+?details\:\s?(.+?)\">.+?HREF=(download.+?)>.+?lista\">(.+?)</td>.+?([0-9\,\.]+ (TB|GB|MB|KB)).+?peers details\">([0-9,]+).+?peers details\">([0-9,]+)",
                    tr,
                )
                if url_titles:
                    timestamp = int(
                        datetime.strptime(url_titles.group(4), "%d/%m/%Y").timestamp()
                    )
                    torrents.append(
                        [
                            quote(f"{self.url}{url_titles.group(3)}"),
                            url_titles.group(2),
                            url_titles.group(5),
                            url_titles.group(7),
                            url_titles.group(8),
                            f"{self.url}{url_titles.group(1)}",
                            timestamp,
                        ]
                    )
            return torrents

    def download_torrent(self, download_url):
        unquoted_magnet = unquote(download_url)
        print(unquoted_magnet + " " + unquoted_magnet)

    def search(self, what, cat="all"):
        what = what.replace("%20", "+")
        parser = self.HTMLParser(self.url)
        counter: int = 0
        while True:
            url = f"{self.url}torrents.php?active=0&search={what}&options=0&order=data&page={counter}"
            html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
            parser.feed(html)
            if parser.noTorrents:
                break
            counter += 1
            sleep(3)