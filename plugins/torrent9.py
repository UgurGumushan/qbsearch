# VERSION: 2.0
"""
Torrent9 (French site) search engine. The real domain changes often, so it is
fetched from a JSON file on GitHub at startup; the class-level url is an
intentional fake used for engine association. Sizes are converted from French
units (e.g. Mo) to English (MB).
"""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar

from helpers import _headers as headers
from helpers import retrieve_url
from novaprinter import SearchResults, prettyPrinter


class torrent9:
    # Intentionally stale fake url: it only anchors engine association, the
    # real domain is resolved at startup (the site changes domains often).
    url = "http://torent9.fr"
    name = "Torrent9 (french)"
    supported_categories: ClassVar[dict[str, list[str]]] = {"all": [""]}

    def __init__(self):
        self.real_url = self.find_url()

    def find_url(self) -> str:
        """Retrieve url from github repository, so it can work even if the url change"""
        link_github = "https://raw.githubusercontent.com/menegop/qbfrench/master/urls.json"
        try:
            req = urllib.request.Request(link_github, headers=headers)
            response = urllib.request.urlopen(req)
            content = response.read().decode()
            urls = json.loads(content)
            return urls["torrent9"][0]

        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return "https://www.torrent9.fm"

    def download_torrent(self, desc_link: str):
        """Download file at url and write it to a file, return the path to the file and the url"""
        file, _path = tempfile.mkstemp()
        file = os.fdopen(file, "wb")
        # Download url
        req = urllib.request.Request(desc_link, headers=headers)
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return ""
        content = response.read().decode()
        pattern = r'"btn btn-danger download" href="(\/.*?)">'

        link = self.real_url + re.findall(pattern, content)[0]
        print(link, desc_link)

    class TableRowExtractor(HTMLParser):
        def __init__(self, url: str, results: list[SearchResults]):
            self.results = results

            self.in_tr = False
            self.in_table_corps = False
            self.in_div_or_anchor = False
            self.current_row: SearchResults = {
                "link": "",
                "name": "",
                "size": "",
                "seeds": -1,
                "leech": -1,
                "engine_url": "",
            }
            self.in_name = False
            self.url = url
            self.item_counter = 0
            self.name_parts: list[str] = []
            super().__init__()

        def handle_starttag(self, tag, attrs):
            if tag == "tbody":
                # check if the table has a class of "table-corps"
                # attrs = dict(attrs)
                # if attrs.get('class') == 'table-corps':
                self.in_table_corps = True

            if self.in_table_corps and tag == "tr":
                self.in_tr = True
                self.item_counter = 0

            if self.in_tr and tag in ["td", "a"]:
                # extract the class name of the div element if it exists
                self.in_div_or_anchor = True

                if tag == "a":
                    attr_map = dict(attrs)
                    href = attr_map.get("href")
                    if href is not None:
                        self.current_row["link"] = self.url + href
                        self.current_row["desc_link"] = self.url + href

            if tag == "h3":
                self.in_name = True
                self.name_parts = []

        def handle_endtag(self, tag):
            if tag == "tr":
                if (
                    self.in_table_corps
                    and "desc_link" in self.current_row
                    and self.current_row.get("desc_link")
                    not in [res.get("desc_link") for res in self.results]
                ):
                    self.results.append(self.current_row)
                self.in_tr = False
                self.current_row = {
                    "link": "",
                    "name": "",
                    "size": "",
                    "seeds": -1,
                    "leech": -1,
                    "engine_url": "",
                }
            if tag == "tbody":
                self.in_table_corps = False
            if tag in ["td", "a"]:
                self.in_div_or_anchor = False
            if tag == "h3":
                self.in_name = False
                self.current_row["name"] = " ".join(self.name_parts)

        def handle_data(self, data):
            if self.in_div_or_anchor:
                if self.in_name:
                    self.name_parts.append(data.strip())
                else:
                    if self.item_counter == 3:
                        self.current_row["size"] = data.strip()
                    if self.item_counter == 5:
                        seeds = data.strip()
                        try:
                            self.current_row["seeds"] = int(seeds)
                        except Exception:
                            pass
                    if self.item_counter == 7:
                        leech = data.strip()
                        try:
                            self.current_row["leech"] = int(leech)
                        except Exception:
                            pass
                    self.item_counter += 1

        def get_rows(self):
            return self.results

    def search(self, what, cat="all"):
        results: list[SearchResults] = []
        len_old_result = 0
        for page in range(10):
            url = f"{self.real_url}/search_torrent/{what}/page-{page + 1}"
            try:
                data = retrieve_url(url)
                parser = self.TableRowExtractor(self.real_url, results)
                parser.feed(data)
                results = parser.results
                parser.close()
            except Exception:
                break

            if len(results) - len_old_result == 0:
                break
            len_old_result = len(results)
        # Sort results
        good_order = [
            ord_res
            for _key, ord_res in sorted(
                zip(
                    [[int(res["seeds"]), int(res["leech"])] for res in results],
                    range(len(results)),
                )
            )
        ]
        results = [results[x] for x in good_order[::-1]]

        # Fix size and add engine
        for res in results:
            res["size"] = unit_fr2en(str(res["size"]))
            res["engine_url"] = self.url
        # Print
        for res in results:
            prettyPrinter(res)


def unit_fr2en(size: str) -> str:
    """Convert french size unit to english"""
    return re.sub(r"([KMGTP])o", lambda match: match.group(1) + "B", size, flags=re.IGNORECASE)


# For testing
# if __name__ == "__main__":
#    engine = torrent9()
