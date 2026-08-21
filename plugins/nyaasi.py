# VERSION: 1.3
"""
Nyaa.si anime search. Parses the HTML results table and follows pagination
(75 rows per page); each row links a magnet or its .torrent file depending on
the use_magent_links flag.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar

# import qBT modules
from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class nyaasi:
    """Class used by qBittorrent to search for torrents."""

    url = "https://nyaa.si"
    name = "Nyaa.si"

    # Whether to use magnet links or download torrent files ###################
    #
    # Set to 'True' to use magnet links, or 'False' to use torrent files
    use_magent_links = True
    #
    ###########################################################################

    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0_0",
        "anime": "1_0",
        "books": "3_0",
        "music": "2_0",
        "pictures": "5_0",
        "software": "6_0",
        "tv": "4_0",
        "movies": "4_0",
    }

    class NyaasiParser(HTMLParser):
        """Parses Nyaa.si browse page for search results and stores them."""

        def __init__(self, res: list[SearchResults], url: str, use_magnet: bool = True):
            """Construct a nyaasi html parser.

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

            self.engine_url: str = url
            self.use_magnet_links: bool = use_magnet
            self.results: list[SearchResults] = res
            self.curr: SearchResults | None = None
            self.td_counter: int = -1

        @staticmethod
        def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            return {key: (value if value is not None else "") for key, value in attrs}

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            """Tell the parser what to do with which tags."""
            if tag == "a":
                self.start_a(attrs)
            elif tag == "td" and self.td_counter == 2 and self.curr is not None:
                ts = self._attrs_to_dict(attrs).get("data-timestamp")
                try:
                    self.curr["pub_date"] = int(ts) if ts is not None else -1
                except ValueError:
                    self.curr["pub_date"] = -1

        def handle_endtag(self, tag: str) -> None:
            """Handle the closing of table cells."""
            if tag == "td":
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle the opening of anchor tags."""
            params = self._attrs_to_dict(attrs)
            # get torrent name
            if "title" in params and "class" not in params and params["href"].startswith("/view/"):
                hit: SearchResults = {
                    "link": "",
                    "name": params["title"],
                    "size": "",
                    "seeds": -1,
                    "leech": -1,
                    "engine_url": self.engine_url,
                    "desc_link": self.engine_url + params["href"],
                }
                if not self.curr:
                    self.curr = hit
            elif "href" in params and self.curr:
                # skip unrelated links
                if not params["href"].startswith("magnet:?") and not params["href"].endswith(
                    ".torrent"
                ):
                    return

                # check whether to use torrent files or magnet links,
                # then search for a matching download link, and move on
                if not self.use_magnet_links and params["href"].endswith(".torrent"):
                    self.curr["link"] = self.engine_url + params["href"]
                    self.td_counter += 1

                elif params["href"].startswith("magnet:?") and self.use_magnet_links:
                    self.curr["link"] = params["href"]
                    self.td_counter += 1

        def start_td(self) -> None:
            """Handle the opening of a table cell tag."""
            # Keep track of timers
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 5 and self.curr is not None:
                self.results.append(self.curr)
                self.curr = None
                self.td_counter = -1

        def handle_data(self, data: str) -> None:
            if self.curr is None:
                return
            """Extract data about the torrent."""
            # These fields matter
            if self.td_counter > 0 and self.td_counter <= 5:
                # Catch the size
                if self.td_counter == 1:
                    self.curr["size"] = data.strip()
                # Catch the seeds
                elif self.td_counter == 3:
                    try:
                        self.curr["seeds"] = int(data.strip())
                    except ValueError:
                        self.curr["seeds"] = -1
                # Catch the leechers
                elif self.td_counter == 4:
                    try:
                        self.curr["leech"] = int(data.strip())
                    except ValueError:
                        self.curr["leech"] = -1
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = "all") -> None:
        """
        Retreive and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                      (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """
        url = str(
            f"{self.url}/?f=0&s=seeders&o=desc&c={self.supported_categories.get(cat)}&q={what}"
        )

        hits: list[SearchResults] = []
        page = 1
        parser = self.NyaasiParser(hits, self.url, self.use_magent_links)
        while True:
            res = retrieve_url(url + f"&p={page}")
            parser.feed(res)
            for each in hits:
                prettyPrinter(each)

            if len(hits) < 75:
                break
            del hits[:]
            page += 1

        parser.close()
