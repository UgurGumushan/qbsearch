# VERSION: 1.3
# AUTHORS: LightDestory (https://github.com/LightDestory)

import re
import urllib.parse

from helpers import retrieve_url, download_file
from novaprinter import prettyPrinter


class yourbittorrent(object):
    url = "https://yourbittorrent.com/"
    name = "YourBittorrent"
    supported_categories = {
        "all": "0",
        "movies": "1",
        "tv": "3",
        "music": "2",
        "games": "4",
        "anime": "6",
        "software": "5",
    }

    # YourBittorrent's page navigation is broken, we can fetch only 50 torrent. Use specific query

    class HTMLParser:
        def __init__(self, url):
            self.url = url
            self.noTorrents = False

        def feed(self, html):
            self.noTorrents = False
            torrents = self.__findTorrents(html)
            resultSize = len(torrents)
            if resultSize == 0:
                self.noTorrents = True
                return
            for torrent in range(resultSize):
                data = {
                    "link": torrents[torrent][0],
                    "name": torrents[torrent][1],
                    "size": torrents[torrent][2],
                    "seeds": torrents[torrent][3],
                    "leech": torrents[torrent][4],
                    "engine_url": self.url,
                    "desc_link": urllib.parse.unquote(torrents[torrent][0]),
                }
                prettyPrinter(data)

        def __findTorrents(self, html):
            torrents = []
            trs = re.findall(
                r'<tr><td class="yb-cell-name">(.+?)</tr>', html, re.DOTALL
            )
            for tr in trs:
                # Extract from the A node all the needed information
                tr = re.sub(r'\stitle="[^"]*"', "", tr)
                url_titles = re.search(
                    r'<a class="yb-tname" href="([^"]+)"[^>]*>(.*?)</a>',
                    tr,
                    re.DOTALL,
                )
                size = re.search(r'data-label="Size">([^<]+)</td>', tr)
                seeds = re.search(r'data-label="Seed">([^<]+)</td>', tr)
                leech = re.search(r'data-label="Peers">([^<]+)</td>', tr)
                if not (url_titles and size):
                    continue
                name = re.sub(r"<[^>]+>", "", url_titles.group(2))
                torrents.append(
                    [
                        urllib.parse.quote(
                            "{0}{1}".format(self.url, url_titles.group(1))
                        ),
                        name,
                        re.sub(r"\s", "", size.group(1)),
                        seeds.group(1) if seeds else "-1",
                        leech.group(1) if leech else "-1",
                    ]
                )
            return torrents

    def download_torrent(self, info):
        torrent_page = retrieve_url(urllib.parse.unquote(info))
        file_link = re.search(r"(down/.+?\.torrent)", torrent_page)
        if file_link and file_link.groups():
            print(download_file(self.url + file_link.groups()[0]))
        else:
            raise Exception("Error, please fill a bug report!")

    def search(self, what, cat="all"):
        what = what.replace("%20", "-")
        parser = self.HTMLParser(self.url)
        category = "" if cat == "all" else f"&c={self.supported_categories[cat]}"
        url = "{0}?q={1}{2}".format(self.url, what, category)
        # Some replacements to format the html source
        html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
        parser.feed(html)
