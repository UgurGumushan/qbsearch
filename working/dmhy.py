# VERSION: 1.00
"""DMHY engine: Chinese anime, donghua, games and music torrents.

Rows are read from the topic-list table, and the .torrent link is
rebuilt from the row date and the magnet's info hash.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar, cast

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class dmhy:
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their corresponding id,
    possible categories are ('all', 'anime', 'books', 'games', 'movies', 'pictures', 'software', 'tv').
    """

    url = 'https://share.dmhy.org'
    name = 'DMHY'
    supported_categories: ClassVar[dict[str, str]]  = {
        'all': '0'
    }

    class RowParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.rows: list[list[str]] = []
            self.in_topic_list = False
            self.depth = 0
            self.cur: dict[str, list[str]] | None = None

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            params = dict(attrs)
            if tag == 'table' and params.get('id') == 'topic_list':
                self.in_topic_list = True
                return
            if not self.in_topic_list:
                return
            if tag == 'tr':
                self.cur = {'raw': [], 'cells': []}
            elif tag == 'td' and self.cur is not None:
                self.cur['cells'].append('')

        def handle_data(self, data: str) -> None:
            if self.cur is not None and self.cur['cells']:
                self.cur['cells'][-1] += data

        def handle_endtag(self, tag: str) -> None:
            if not self.in_topic_list:
                return
            if tag == 'tr' and self.cur is not None:
                self.rows.append(self.cur['cells'])
                self.cur = None
            elif tag == 'table':
                self.in_topic_list = False

    @classmethod
    def analyze_torrent(cls, cells: list[list[str]]) -> list[SearchResults]:
        res: list[SearchResults] = []
        for cell in cells:
            if len(cell) < 7:
                continue
            date = re.sub(r'\s+', ' ', cell[0]).strip().split()[0]
            name = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[2])).strip()
            links = re.findall(r'href="([^"]*)"', cell[3])
            magnet = next((l for l in links if l.startswith('magnet:?')), '')
            desc_m = re.search(r'href="([^"]*)"', cell[2])
            desc_link = f"{cls.url}{desc_m.group(1)}" if desc_m else cls.url
            size = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[4])).strip()
            seeds = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[5])).strip()
            leech = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[6])).strip()
            btih_m = re.search(r'btih:([0-9A-Fa-f]+)', magnet)
            link = f"https://dl.dmhy.org/{date}/{btih_m.group(1)}.torrent" if btih_m else magnet
            tmp: dict[str, str | int] = {
                'date': date,
                'name': name,
                'desc_link': desc_link,
                'engine_url': cls.url,
                'size': size,
                'seeds': int(seeds) if seeds.isdigit() else -1,
                'leech': int(leech) if leech.isdigit() else -1,
                'link': link,
            }
            # Keep the date field in the returned scraper record; qBittorrent's
            # printer contract only describes the common result fields.
            result = cast(SearchResults, cast(object, tmp))
            res.append(result)
            prettyPrinter(result)
        return res

    def download_torrent(self, info: str) -> None:
        """
        Providing this function is optional.
        It can however be interesting to provide your own torrent download
        implementation in case the search engine in question does not allow
        traditional downloads (for example, cookie-based download).
        """
        print(download_file(info))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = 'all') -> None:
        """
        Here you can do what you want to get the result from the search engine website.
        Everytime you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `what` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `cat` is the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """
        hits: list[SearchResults] = []
        url = self.url
        page = 1

        while True:
            res = retrieve_url(f"{url}/topics/list/page/{page}?keyword={what.replace(' ', '+')}")
            parser = self.RowParser()
            parser.feed(res)
            parser.close()
            cells = parser.rows
            hits.extend(self.analyze_torrent(cells))
            page += 1
            if len(cells) < 80:
                break


if __name__ == '__main__':
    d = dmhy()
    d.search('C3魔方少女')
    print(1)
