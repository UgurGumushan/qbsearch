# VERSION: 1.0
"""acg.rip engine: anime, manga, games and software search results.

Links are torrent-file downloads; result pages are followed one page at a
time until a short page is returned.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar

# qBittorrent nova3 modules
from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class acgrip:
    """qBittorrent search engine for acg.rip."""

    url = 'https://acg.rip'
    name = 'acg.rip'

    ###########################################################################

    # Map the qBittorrent search categories to the engine's own ids.
    # Possible categories: 'all', 'movies', 'tv', 'music', 'games', 'anime',
    # 'software', 'pictures', 'books'.
    supported_categories: ClassVar[dict[str, str]]  = {'all': '0_0'}

    class acgripParser(HTMLParser):
        """Parse an acg.rip results page and store the parsed hits."""

        def __init__(self, res: list[SearchResults], url: str) -> None:
            """Construct a acgrip html parser.

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
            self.results = res
            self.curr: SearchResults | None = None
            self.td_counter = -1
            self.find_title = False
            self.span_counter = -1

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            """Dispatch opening tags to the matching helper."""
            if tag == 'a':
                self.start_a(attrs)
            if tag == 'span':
                self.start_span(attrs)

        def handle_endtag(self, tag: str) -> None:
            """Handle closing table-cell tags."""
            if tag == 'td':
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle opening anchor tags."""
            params = dict(attrs)
            href = params.get('href') or ''
            # Topic link: starts a new result row.
            if 'class' not in params and not href.endswith(".torrent")\
                    and href.startswith('/t/'):
                hit: SearchResults = {
                    'link': '',
                    'name': '',
                    'size': '',
                    'seeds': -1,
                    'leech': -1,
                    'engine_url': self.engine_url,
                    'desc_link': self.engine_url + href,
                }
                self.td_counter += 1
                if not self.curr:
                    self.curr = hit
            elif 'href' in params and self.curr:
                # skip unrelated links
                if not href.endswith(".torrent"):
                    return

                # check whether to use torrent files or magnet links,
                # then search for a matching download link, and move on
                if href.endswith(".torrent"):
                    self.curr['link'] = self.engine_url + href

        def start_span(self, attrs: list[tuple[str, str | None]]) -> None:
            """Track which of the seeds/leech spans in a row's stats cell."""
            params = dict(attrs)
            class_name = params.get('class') or ''
            if class_name == 'title':
                self.find_title = True
            elif class_name and not class_name.startswith('label'):
                if self.span_counter == -1:
                    self.span_counter += 1
                elif self.span_counter == 2:
                    self.span_counter -= 1
            else:
                pass

        def start_td(self) -> None:
            """Handle the opening of a table cell tag."""
            # Count the row's cells until the row is complete.
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 4:
                if self.curr is not None:
                    self.results.append(self.curr)
                self.curr = None
                self.td_counter = -1
                self.find_title = False
                self.span_counter = -1

        def handle_data(self, data: str) -> None:
            """Extract data about the torrent."""
            if self.curr is None:
                return
            if self.td_counter > -1\
                    and self.td_counter <= 4:
                # Row 0 carries the torrent name.
                if self.find_title and self.td_counter == 0:
                    self.curr['name'] = data.strip()
                    self.find_title = False
                # Catch the size
                elif self.td_counter == 2:
                    self.curr['size'] = data.strip()
                elif self.td_counter == 3:
                    # Catch the seeds
                    if self.span_counter == 0:
                        try:
                            self.span_counter += 2
                            self.curr['seeds'] = int(data.strip())
                        except ValueError:
                            self.curr['seeds'] = -1
                    # Catch the leech
                    elif self.span_counter == 1:
                        try:
                            self.span_counter += 2
                            self.curr['leech'] = int(data.strip())
                        except ValueError:
                            self.curr['leech'] = -1
                    else:
                        pass
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
        url = self.url

        hits: list[SearchResults] = []
        page = 1
        parser = self.acgripParser(hits, self.url)
        while True:
            res = retrieve_url(f'{url}/page/{page}?term={what}')
            parser.feed(res)
            for each in hits:
                prettyPrinter(each)

            if len(hits) < 30:
                break
            del hits[:]
            page += 1

        parser.close()
