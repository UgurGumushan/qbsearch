# VERSION: 2.3
"""
Tokyo Toshokan (http://tokyotosho.info, anime site) search engine. Scrapes
the listing table; further pages are followed via ?lastid=&page= links found
in the last page, batched five pages at a time.
"""

from __future__ import annotations

from html.parser import HTMLParser
from re import compile as re_compile

from helpers import download_file, retrieve_url

# qBt
from novaprinter import SearchResults, prettyPrinter


def stats_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return -1


class tokyotoshokan:
    url = "http://tokyotosho.info"
    name = "Tokyo Toshokan"

    global page_count
    page_count = 1

    def __init__(self):
        self.supported_categories = {"all": "0", "anime": "1", "games": "14"}
        # self.supported_categories = {'all': '0', 'anime': '1', 'anime(non-english)': '10',
        #                        'manga': '3', 'drama': '8', 'music': '2',
        #                        'music video': '9', 'raw': '7', 'hentai': '4',
        #                        'eroge': '14', 'batch': '11', 'jav': '15', 'other': '5'}
        #

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    class MyHtmlParseWithBlackJack(HTMLParser):
        def __init__(self, url: str):
            HTMLParser.__init__(self)
            self.get_size_regex = re_compile(r".*Size:\s+([^ ]*)\s+.*")
            self.url = url
            self.current_item: dict[str, str] | None = None
            self.size_found = False
            self.name_found = False
            self.stats_found = False
            self.stat_name: str | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if self.current_item:
                if tag == "a":
                    href: str | None = params.get("href")
                    if isinstance(href, str) and href.startswith("magnet"):
                        self.current_item["link"] = href
                    elif "type" in params and params["type"] == "application/x-bittorrent":
                        self.name_found = True
                        self.current_item["name"] = ""
                    elif isinstance(href, str) and href.startswith("details"):
                        self.current_item["desc_link"] = f"{self.url}/{href}"

                elif tag == "td" and "class" in params:
                    if params.get("class") == "desc-bot":
                        self.size_found = True
                        self.current_item["size"] = "Unknown"
                    elif params.get("class") == "stats":
                        self.stats_found = True

                elif self.stats_found and tag == "span":
                    self.stat_name = "leech" if "seeds" in self.current_item else "seeds"

            elif tag == "tr" and (params.get("class") or "").find("category"):
                self.current_item = {}
                self.current_item["engine_url"] = self.url

        def handle_endtag(self, tag: str) -> None:
            if tag == "a":
                if self.name_found:
                    self.name_found = False
            elif tag == "span":
                self.stat_name = None
            elif self.current_item and tag == "tr" and len(self.current_item) == 7:
                raw = self.current_item
                res: SearchResults = {
                    "link": raw["link"],
                    "name": raw["name"],
                    "size": raw["size"],
                    "seeds": stats_int(raw["seeds"]),
                    "leech": stats_int(raw["leech"]),
                    "engine_url": raw["engine_url"],
                    "desc_link": raw["desc_link"],
                }
                prettyPrinter(res)
                self.current_item = None
                self.size_found = False
                self.name_found = False
                self.stats_found = False
                self.stat_name = None

        def handle_data(self, data: str) -> None:
            if self.current_item is None:
                return
            if self.name_found:
                self.current_item["name"] += data
            elif self.size_found:
                # There can be several pieces.
                result = self.get_size_regex.search(data)
                if result:
                    self.current_item["size"] = result.group(1)
                    self.size_found = False
            elif self.stat_name:
                self.current_item[self.stat_name] = data

    def handle_more_pages(
        self,
        last_page_url: str,
        parser: MyHtmlParseWithBlackJack,
        query: str,
        skip_first: bool = False,
    ) -> str:
        torrent_list = re_compile('(?s)<table class="listing">(.*)</table>')
        additional_links = re_compile(
            r"\?lastid=[0-9]+&page=[0-9]+&terms={}".format(query.replace("%20", "\\+"))
        )

        data: str = retrieve_url(last_page_url)
        m = torrent_list.search(data)
        if m:
            data = m.group(0)

        for res_link in (
            "".join((self.url, "/search.php", link.group(0)))
            for link in additional_links.finditer(data)
        ):
            if skip_first:
                skip_first = False
                continue

            global page_count
            page_count += 1
            last_page_url = res_link
            data = retrieve_url(res_link)
            m = torrent_list.search(data)
            if m:
                data = m.group(0)
            parser.feed(data)
            parser.close()

        return last_page_url

    def search(self, query: str, cat: str = "all") -> None:
        query = query.replace(" ", "+")
        parser = self.MyHtmlParseWithBlackJack(self.url)
        last_page_url = ""
        page_multiplier = 1
        torrent_list = re_compile('(?s)<table class="listing">(.*)</table>')
        request_url = f"{self.url}/search.php?terms={query}&type={self.supported_categories[cat]}&size_min=&size_max=&username="
        data: str = retrieve_url(request_url)

        m = torrent_list.search(data)
        if m:
            data = m.group(0)
        parser.feed(data)
        parser.close()

        last_page_url = self.handle_more_pages(request_url, parser, query)

        while True:
            if page_count > (page_multiplier * 5):
                last_page_url = self.handle_more_pages(last_page_url, parser, query, True)
                page_multiplier += 1
            else:
                break
