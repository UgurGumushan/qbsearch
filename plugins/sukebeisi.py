#VERSION: 1.11
"""
Sukebei (https://sukebei.nyaa.si, an adult / anime-art site) search engine.
Scrape-based with HTML parsing; pages of 75 results are fetched until a page
returns fewer than 75 hits.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar, TypedDict, cast

# import qBT modules
from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class SukebeiRow(TypedDict, total=False):
    link: str
    name: str
    size: str
    seeds: int
    leech: int
    engine_url: str
    desc_link: str


class sukebeisi:
    """Class used by qBittorrent to search for torrents"""

    url = 'https://sukebei.nyaa.si'
    name = 'Sukebei (Nyaa)'
    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books'
    # Anime     = sukebei.nyaa's "Art - Anime"
    # Books     = sukebei.nyaa's "Art - Doujinshi"
    # Games     = sukebei.nyaa's "Art - Games"
    # Pictures  = sukebei.nyaa's "Real Life - Photobooks and Pictures"
    # Movies    = sukebei.nyaa's "Real Life - Videos"
    # If you wish to enable other categories by editing this list or by using one of the unused supported categories (music, software) they are:
    # Top level "Art" category = '1_0'
    # Top level "Real Life" category = '2_0'
    # "Art - Manga" and "Art - Pictures" are included as commented examples below.
    # Simply replace line 53 or 55 with the examples below
    #   'books': '1_4',
    #   'pictures': '1_5',
    supported_categories: ClassVar[dict[str, str]]  = {
            'all': '0_0',
            'anime': '1_1',
            'books': '1_2',
            'games': '1_3',
            'pictures': '2_1',
            'movies': '2_2'}

    class SukebeiSiParser(HTMLParser):
        """ Parses sukebei.nyaa.si browse page for search results and prints them"""
        def __init__(self, res: list[SukebeiRow], url: str) -> None:
            try:
                super().__init__()
            except Exception:#  See: http://stackoverflow.com/questions/9698614/
                HTMLParser.__init__(self)

            self.engine_url = url
            self.results: list[SukebeiRow] = res
            self.curr: SukebeiRow | None = None
            self.td_counter = -1

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            """Tell the parser what to do with which tags"""
            if tag == 'a':
                self.start_a(attrs)

        def handle_endtag(self, tag: str) -> None:
            if tag == 'td':
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            params = {key: value for key, value in attrs if value is not None}
            title = params.get('title')
            href = params.get('href')
            # get torrent name
            if (
                title is not None
                and href is not None
                and 'class' not in params
                and href.startswith('/view/')
            ):
                hit: SukebeiRow = {
                    'name': title,
                    'desc_link': self.engine_url + href,
                }
                if self.curr is None:
                    hit['engine_url'] = self.engine_url
                    self.curr = hit
            elif href is not None and href.startswith("magnet:?"):
                if self.curr is not None:
                    self.curr['link'] = href
                    self.td_counter += 1

        def start_td(self) -> None:
            # Keep track of timers
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 5:
                if self.curr is not None:
                    self.results.append(self.curr)
                self.curr = None
                self.td_counter = -1

        def handle_data(self, data: str) -> None:
            if self.curr is None:
                return
            # These fields matter
            if self.td_counter > 0 and self.td_counter <= 5:
                # Catch the size
                if self.td_counter == 1:
                    self.curr['size'] = data.strip()
                # Catch the seeds
                elif self.td_counter == 3:
                    try:
                        self.curr['seeds'] = int(data.strip())
                    except Exception:self.curr['seeds'] = -1
                # Catch the leechers
                elif self.td_counter == 4:
                    try:
                        self.curr['leech'] = int(data.strip())
                    except Exception:self.curr['leech'] = -1
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = 'all') -> None:
        """
        Retrieve and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                     (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """

        url = str(f"{self.url}/?f=0&s=seeders&o=desc&c={self.supported_categories.get(cat)}&q={what}"
                  )

        hits: list[SukebeiRow] = []
        page = 1
        parser = self.SukebeiSiParser(hits, self.url)
        while True:
            res = retrieve_url(url + f"&p={page}")
            parser.feed(res)
            for each in hits:
                prettyPrinter(cast(SearchResults, cast(object, each)))

            if len(hits) < 75:
                break
            del hits[:]
            page += 1

        parser.close()
