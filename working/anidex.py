# VERSION: 0.02
"""AniDex engine: anime, games, music and other niche category search.

All additional result pages are fetched concurrently in threads (offset
pagination) and results are magnet links.
"""
from __future__ import annotations

import re
import threading
import time
from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class anidex:
    url = 'https://anidex.info/'
    name = 'AniDex'
    supported_categories: ClassVar[dict[str, str]]  = {
        'all': '',
        'music': 'id=9,10,11&',
        'games': 'id=12&',
        'anime': 'id=1,2,3&',
        'software': 'id=13&',
        'pictures': 'id=14&',
        'books': 'id=6,7,8&',
    }

    class anidexParser(HTMLParser):
        url = 'https://anidex.info'
        TR, TH, TD, A, SPAN = 'tr', 'th', 'td', 'a', 'span'
        inRow = False
        getSize = False
        getSeed = False
        getLeech = False
        def __init__(self) -> None:
            super().__init__()
            self.this_result: SearchResults = {
                'link': '',
                'name': '',
                'size': '',
                'seeds': -1,
                'leech': -1,
                'engine_url': self.url,
            }

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag == self.TR and self.inRow is False:
                self.inRow = True
            if tag == self.TH and self.inRow is True:
                self.inRow = False
            if self.inRow is True and tag == self.TD:
                my_attrs = dict(attrs)
                if my_attrs.get('class') == 'text-center td-992' and my_attrs.get('title') is None:
                    self.getSize = True
                if my_attrs.get('class') == 'text-success text-right':
                    self.getSeed = True
                if my_attrs.get('class') == 'text-danger text-right':
                    self.getLeech = True
            if self.inRow and tag == self.A:
                my_attrs = dict(attrs)
                href = my_attrs.get('href')
                if href is not None and href.startswith('magnet'):
                    self.this_result['link'] = href
                if my_attrs.get('class') == 'torrent':
                    self.this_result['desc_link'] = self.url + (href or '')
            if self.inRow and tag == self.SPAN:
                my_attrs = dict(attrs)
                title = my_attrs.get('title')
                if my_attrs.get('class') == 'span-1440' and title is not None:
                    self.this_result['name'] = title

        def handle_endtag(self, tag: str) -> None:
            if self.inRow is True and tag == self.TR:
                self.inRow = False
                self.this_result['engine_url'] = self.url
                prettyPrinter(self.this_result)

        def handle_data(self, data: str) -> None:
            if self.inRow and self.getSize:
                self.this_result['size'] = data.strip().replace(',', '')
                self.getSize = False
            if self.inRow and self.getSeed:
                seed_value = data.strip().replace(',', '')
                self.this_result['seeds'] = int(seed_value) if seed_value.isdigit() else -1
                self.getSeed = False
            if self.inRow and self.getLeech:
                leech_value = data.strip().replace(',', '')
                self.this_result['leech'] = int(leech_value) if leech_value.isdigit() else -1
                self.getLeech = False

    def do_search(self, url: str) -> None:
        webpage = retrieve_url(url)
        adexParser = self.anidexParser()
        adexParser.feed(webpage)

    def search(self, what: str, cat: str = 'all') -> None:
        query = str(what).replace(' ', '+')
        search_url = self.url + \
            '?s=seeders&o=desc&' + \
            self.supported_categories[cat.lower()] + \
            'q=' + query

        webpage = retrieve_url(search_url)
        total_results = re.findall(r'Showing[^f]+f(.+?)torrents', webpage)[0].strip().replace(',', '')
        total_results = int(total_results)

        adexParser = self.anidexParser()
        adexParser.feed(webpage)

        threads: list[threading.Thread] = []
        for offset in range(50, total_results, 50):
            this_url = search_url + '&offset=' + str(offset)
            t = threading.Thread(args=(this_url,), target=self.do_search)
            time.sleep(2)
            t.start()
            threads.append(t)
            # self.do_search(this_url)

        for t in threads:
            t.join()


if __name__ == '__main__':
    a = anidex()
    a.search('DS', 'all')
