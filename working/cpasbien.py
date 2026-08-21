# VERSION: 2.2
"""Cpasbien (French) engine: movies and TV torrents.

The current site domain is pulled from a public URL file since the site
moves often; sizes arrive in French units (ex. 'Ko') which are converted.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from typing import ClassVar

logger = logging.getLogger()

from html.parser import HTMLParser

from helpers import _headers as headers
from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class cpasbien:
    # This is a fake url only for engine associations in file download
    url = "http://www.cpasbien.fr"
    name = "Cpasbien (french)"
    results_per_page = 50
    supported_categories: ClassVar[dict[str, list[str]]] = {"all": [""]}

    def __init__(self) -> None:
        self.real_url: str = self.find_url()
        logger.debug("Cpasbien URL: %s", self.real_url)

    def find_url(self) -> str:
        """Fetch the current site domain from a GitHub URL file so the engine
        keeps working when the domain moves."""
        link_github = "https://raw.githubusercontent.com/MarcBresson/cpasbien/master/cpasbien.url"
        try:
            req = urllib.request.Request(link_github, headers=headers)
            response = urllib.request.urlopen(req)
            content: str = response.read().decode()
            cpasbien_url = content.strip()
            return cpasbien_url

        except urllib.error.URLError as e:
            default_url = "http://www.cpasbien.biz"

            if str(e.reason).lower() == "not found":
                logger.warning(
                    "Could not find URL '%s', defaulting to '%s'", link_github, default_url
                )
            else:
                logger.warning(
                    "Error '%s' while tring to find the current cpasbien URL, defaulting to '%s'",
                    e.reason,
                    default_url,
                )
            return default_url

    def download_torrent(self, desc_link: str) -> None:
        """find the link to the torrent"""
        logger.debug("Looking for the torrent download link at URL %s", desc_link)
        req = urllib.request.Request(desc_link, headers=headers)

        try:
            response = urllib.request.urlopen(req)
        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return

        content = response.read().decode()

        link = self.real_url + re.findall(r'<a href="(/get_torrent/.*?)">', content)[0]
        logger.info("Found torrent download link with URL %s", link)

        print(download_file(link))

    def search(self, what: str, cat: str | None = None) -> None:
        results: list[SearchResults] = []
        len_old_result = 0
        for page in range(10):
            url = f"{self.real_url}/recherche/{what}/{page * self.results_per_page + 1}"

            parser = TableRowExtractor(self.real_url, self.url, results)

            try:
                data = retrieve_url(url)
            except urllib.error.URLError as errno:
                print(" ".join(("Connection error:", str(errno.reason))))
                break

            parser.feed(data)
            results.extend(parser.results)
            parser.close()

            # if there is no new result on the page, stop the search
            if len(results) - len_old_result == 0:
                break

            len_old_result = len(results)

        # Sort results
        good_order = [
            ord_res
            for _, ord_res in sorted(
                zip(
                    [[int(res["seeds"]), int(res["leech"])] for res in results], range(len(results))
                )
            )
        ]
        results = [results[x] for x in good_order[::-1]]

        logger.info("found %d torrents from cpasbien search engine", len(results))

        # Add engine
        for res in results:
            res["engine_url"] = self.url
        # Print
        for res in results:
            prettyPrinter(res)


class TableRowExtractor(HTMLParser):
    map_name: dict[str, str]
    current_div_class: str = ""

    def __init__(self, url: str, engine_url: str, results: list[SearchResults]):
        self.results = results
        self.map_name = {"titre": "name", "poid": "size", "up": "seeds", "down": "leech"}
        self.in_tr = False
        self.in_table_corps = False
        self.in_div_or_anchor = False
        self.current_row: dict[str, str] = {}
        self.url = url
        self.engine_url = engine_url
        super().__init__()

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            # Only the results table (class "table-corps") is parsed.
            attrs = dict(attrs)
            if attrs.get("class") == "table-corps":
                self.in_table_corps = True

        if self.in_table_corps and tag == "tr":
            self.in_tr = True

        if self.in_tr and tag in ["div", "a"]:
            # Map the cell's class ("titre", "poid", "up", "down") to a result
            # field so the following text lands in the right column.
            self.in_div_or_anchor = True
            attrs = dict(attrs)
            self.current_div_class = self.map_name.get(attrs.get("class") or "", "")
            if tag == "a" and self.current_div_class == "name":
                href = attrs.get("href")
                if href is not None:
                    self.current_row["link"] = self.url + href
                    self.current_row["desc_link"] = self.url + href

    def handle_endtag(self, tag):
        if tag == "tr":
            if (
                self.in_table_corps
                and "desc_link" in self.current_row
                and self.current_row["desc_link"]
                not in [res.get("desc_link") for res in self.results]
            ):
                self.results.append(
                    SearchResults(
                        link=self.current_row["link"],
                        name=self.current_row["name"],
                        size=unit_fr2en(self.current_row["size"]),
                        seeds=int(self.current_row["seeds"]),
                        leech=int(self.current_row["leech"]),
                        engine_url=self.engine_url,
                        desc_link=self.current_row["desc_link"],
                    )
                )
            self.in_tr = False

            self.current_row = {}
        if tag == "table":
            self.in_table_corps = False
        if tag in ["div", "a"]:
            self.in_div_or_anchor = False

    def handle_data(self, data):
        if self.in_div_or_anchor and self.current_div_class:
            self.current_row[self.current_div_class] = data

    def get_rows(self) -> list[SearchResults]:
        return self.results


def unit_fr2en(size: str) -> str:
    """Convert French size units (Ko, Mo, ...) to English (KB, MB, ...)."""
    return re.sub(r"([KMGTP])o", lambda match: match.group(1) + "B", size, flags=re.IGNORECASE)
