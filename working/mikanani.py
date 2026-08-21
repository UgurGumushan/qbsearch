# VERSION: 1.2
"""
MikanProject (mikanime.tv) anime search. Parses the HTML search results page;
each row links its detail page and its .torrent file.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar, TypedDict, cast

try:
    import requests
except ModuleNotFoundError:
    requests = None
from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class MikananiRow(TypedDict, total=False):
    link: str
    name: str
    size: str
    seeds: int
    leech: int
    engine_url: str
    desc_link: str


class mikanani:
    """Class used by qBittorrent to search for torrents."""

    url = 'https://mikanime.tv'
    name = 'mikanani'

    ###########################################################################

    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories: ClassVar[dict[str, str]]  = {'all': ''}

    class mikananiParser(HTMLParser):
        """Parses a mikanime.tv search page for results and stores them."""

        def __init__(self, res: list[SearchResults], url: str) -> None:
            """Construct a mikanime.tv HTML parser.

            Parameters:
            :param list res: a list to store the results in
            :param str url: the base url of the search engine
            :param str use_magnet: whether to link to magnet links or torrent
                                   files
            """
            try:
                super().__init__()
            except TypeError:
                #  See: http://stackoverflow.com/questions/9698614/
                HTMLParser.__init__(self)

            self.engine_url = url
            self.results: list[SearchResults] = res
            self.curr: MikananiRow | None = None
            self.td_counter = -1
            self.span_counter = 0
            self.find_title = False

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            """Tell the parser what to do with which tags."""
            if tag == 'a':
                self.start_a(attrs)

        def handle_endtag(self, tag: str) -> None:
            """Handle the closing of table cells."""
            if tag == 'td':
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle the opening of anchor tags."""
            params = {key: value for key, value in attrs if value is not None}
            css_class = params.get('class')
            href = params.get('href')
            # get torrent name
            if (
                css_class is not None
                and css_class.startswith('magnet')
                and 'target' in params
                and href is not None
            ):
                self.find_title = True
                hit: MikananiRow = {'desc_link': self.engine_url + href}
                self.td_counter += 1
                if self.curr is None:
                    hit['engine_url'] = self.engine_url
                    hit['seeds'] = -1
                    hit['leech'] = -1
                    self.curr = hit
            elif href is not None and self.curr is not None:
                # skip unrelated links
                if not href.endswith(".torrent"):
                    return

                # check whether to use torrent files or magnet links,
                # then search for a matching download link, and move on
                if href.endswith(".torrent"):
                    self.curr['link'] = self.engine_url + href
            else:
                pass

        def start_td(self) -> None:
            """Handle the opening of a table cell tag."""
            # Keep track of timers
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 4:
                if self.curr is not None:
                    self.results.append(cast(SearchResults, cast(object, self.curr)))
                self.curr = None
                self.td_counter = -1
                self.find_title = False
                self.span_counter = -1

        def handle_data(self, data: str) -> None:
            """Extract data about the torrent."""
            if self.curr is None:
                return
            # These fields matter
            if self.td_counter > -1\
                    and self.td_counter <= 4:
                # Catch the name
                if self.find_title and self.td_counter == 0:
                    self.curr['name'] = data.strip()
                    self.find_title = False
                # Catch the size
                elif self.td_counter == 1:
                    self.curr['size'] = data.strip()
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py

    def search(self, what: str, cat: str = 'all') -> None:
        """
        Retreive and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                     (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """
        url = self.url

        # print(url)
        hits: list[SearchResults] = []
        page = 1
        parser = self.mikananiParser(hits, self.url)
        while True:
            requirement = f'{url}/Home/Search?page={page}&searchstr={what}&subgroupid={cat}'
            # s = requests.Session()
            # res = new_retrieve_url(requirement,s)
            res = retrieve_url(requirement)
            # print(res)
            parser.feed(res)
            # print(hits)
            for each in hits:
                prettyPrinter(each)

            # if len(hits) < 30:
            #     break
            # del hits[:]
            # page += 1
            break

        parser.close()


def new_retrieve_url(url: str, s: object) -> str:
    """ Return the content of the url page as a string """
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    headers = {'User-Agent': user_agent}
    s = requests.Session()  # pyright: ignore[reportOptionalMemberAccess]
    response = s.get(url, headers=headers)

    dat = response.text
    # return dat.encode('utf-8', 'replace')
    return dat
