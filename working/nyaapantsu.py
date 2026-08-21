# VERSION: 1.2
"""
Nyaa.pantsu anime search. Parses the HTML results table (name, size, seeds,
leeches) and follows pagination up to 300 results per page until the site
returns a short page.
"""

from __future__ import annotations

from enum import Enum
from html.parser import HTMLParser
from typing import ClassVar

# import qBT modules
from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class nyaapantsu:
    """Class used by qBittorrent to search for torrents"""

    url = "https://nyaa.pantsu.cat"
    name = "Nyaa.pantsu"
    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "_",
        "anime": "3_",
        "books": "4_",
        "music": "2_",
        "pictures": "6_",
        "software": "1_",
        "tv": "5_",
        "movies": "5_",
    }

    class NyaaPantsuParser(HTMLParser):
        """Parses Nyaa.pantsu browse page for search resand prints them"""

        class DataType(Enum):
            """Enumeration to keep track of the TD Type to use in handle_data()'"""

            NONE = 0
            NAME = 1
            SEEDS = 2
            LEECH = 3
            SIZE = 4

        def __init__(
            self,
            res: list[SearchResults],
            url: str = "https://nyaa.pantsu.cat",
        ):
            try:
                super().__init__()
            except Exception:  #  See: http://stackoverflow.com/questions/9698614/
                HTMLParser.__init__(self)

            self.engine_url: str = url
            self.results: list[SearchResults] = res
            self.curr: dict[str, str | int] | None = None
            self.td_type = self.DataType.NONE

        @staticmethod
        def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            return {key: (value if value is not None else "") for key, value in attrs}

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            """Calls element specific functions based on tag."""
            if tag == "a":
                self.start_a(attrs)
            if tag == "tr":
                self.start_tr(attrs)
            if tag == "td":
                self.start_td(attrs)

        def start_tr(self, attr: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attr)
            if "class" in params and params["class"].startswith("torrent-info"):
                self.curr = {"engine_url": self.engine_url}

        def start_a(self, attr: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attr)
            # get torrent name
            if "href" in params and params["href"].startswith("/view/"):
                if self.curr:
                    self.curr["desc_link"] = self.engine_url + params["href"]
                # also get name from handle_data()
                self.td_type = self.DataType.NAME
            # get torrent magnet link
            elif "href" in params and params["href"].startswith("magnet:?"):
                if self.curr:
                    self.curr["link"] = params["href"]

        def start_td(self, attr: list[tuple[str, str | None]]) -> None:
            """Parses TD elements and sets self.td_type based on its html class.

            If last TD element for the current hit is reached it appends it to
            results and cleans up.
            """
            params = self._attrs_to_dict(attr)

            # get seeds from handle_data()
            if "class" in params and params["class"].startswith("tr-se"):
                self.td_type = self.DataType.SEEDS
            # get leechers from handle_data()
            elif "class" in params and params["class"].startswith("tr-le"):
                self.td_type = self.DataType.LEECH
            # get size from handle_data()
            elif "class" in params and params["class"].startswith("tr-size"):
                self.td_type = self.DataType.SIZE
            # we've reached the end of this result; save it and clean up.
            elif "class" in params and params["class"].startswith("tr-date"):
                if self.curr is not None:
                    self.results.append(
                        SearchResults(
                            link=str(self.curr.get("link", "")),
                            name=str(self.curr.get("name", "")),
                            size=str(self.curr.get("size", "")),
                            seeds=int(self.curr.get("seeds", -1)),
                            leech=int(self.curr.get("leech", -1)),
                            engine_url=str(self.curr.get("engine_url", "")),
                            desc_link=str(self.curr.get("desc_link", "")),
                        )
                    )
                self.td_type = self.DataType.NONE
                self.curr = None
            # default: current innerContent does not concern us: pass.
            else:
                self.td_type = self.DataType.NONE

        def handle_data(self, data: str) -> None:
            """Strip textContent data for search result based on td type"""
            if self.curr is None:
                return
            # Get result name
            if self.td_type == self.DataType.NAME:
                name = str(self.curr.get("name", ""))
                name += data.strip()
                self.curr["name"] = name
                self.td_type = self.DataType.NONE
            # Get no. of seeds
            elif self.td_type == self.DataType.SEEDS:
                try:
                    self.curr["seeds"] = int(data.strip())
                except Exception:
                    self.curr["seeds"] = -1
                finally:
                    self.td_type = self.DataType.NONE
            # Get no. of leechers
            elif self.td_type == self.DataType.LEECH:
                try:
                    self.curr["leech"] = int(data.strip())
                except Exception:
                    self.curr["leech"] = -1
                finally:
                    self.td_type = self.DataType.NONE
            # Get size
            elif self.td_type == self.DataType.SIZE:
                self.curr["size"] = data.strip()
                self.td_type = self.DataType.NONE
            # Default: self.td_type is unset, current textConent is not
            # interesting, do nothing.
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

        page = 1
        hits: list[SearchResults] = []
        parser = self.NyaaPantsuParser(hits, self.url)
        while True:
            url = str(
                f"{self.url}/search/{page}?s=0&sort=5&order=false&max=300&c="
                f"{self.supported_categories.get(cat)}&q={what}"
            )
            # pantsu is very volatile.
            try:
                res = retrieve_url(url)
                parser.feed(res)
            except Exception:
                pass

            for each in hits:
                prettyPrinter(each)

            if len(hits) < 300:
                break
            del hits[:]
            page += 1

        parser.close()
