# VERSION: 1.0
"""CalidadTorrent engine: Spanish movies, series and anime torrents.

Each torrent card is followed to grab its .torrent link, and all result
pages are parsed until the site reports no more matches.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class calidadtorrent:
    url = 'https://calidadtorrent.com'
    headers: dict[str, str] = {  # noqa: RUF012
        'Referer': url
    }
    name = 'CalidadTorrent'
    supported_categories: ClassVar[dict[str, str]] = {
        'all': 'all'
    }

    no_results_regex = r'<p.*?>No se ha encontrado ning[uú]n resultado.</p>'

    class SearchResultsParser(HTMLParser):
        def error(self, message: str) -> None:
            pass

        DIV, A = ('div', 'a')

        expected_x_data = "{ showDetail: true }"
        torrent_link_regex = r'\/torrents\/.+?\.torrent'
        title_regex = r'<h1.*?>.*?</h1>'

        count = 0

        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.headers = {
                'Referer': url
            }

            self.insideResultList = False
            self.insideResultContainer = False
            self.insideResult = False
            self.insideLink = False

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            params = dict(attrs)
            css_classes = params.get('class') or ''
            x_data = params.get('x-data')

            if tag == self.DIV and 'result-list' in css_classes:
                self.insideResultList = True
                return

            if self.insideResultList and tag == self.DIV and x_data == self.expected_x_data:
                self.insideResultContainer = True
                return

            if self.insideResultContainer and tag == self.DIV and 'relative' in css_classes:
                self.insideResult = True
                return

            if self.insideResult and tag == self.A:
                self.count += 1
                self.insideLink = True
                href = params.get('href')
                if href is None:
                    return
                retrieved_html = retrieve_url(href, self.headers)

                link_matches = re.finditer(self.torrent_link_regex, retrieved_html, re.MULTILINE)
                title_matches = re.finditer(self.title_regex, retrieved_html, re.MULTILINE)

                torrent_link = [x.group() for x in link_matches]
                title = [x.group() for x in title_matches]

                row: SearchResults = {
                    'link': f'{calidadtorrent.url}{torrent_link[0]}',
                    'name': re.sub(r'</h1>', '',re.sub(r'<h1.+?>', '', title[0])),
                    'size': 0,
                    'seeds': -1,
                    'leech': -1,
                    'engine_url': calidadtorrent.url,
                    'desc_link': href
                }
                prettyPrinter(row)
                return

        def handle_endtag(self, tag: str) -> None:
            if self.insideLink and tag == self.A:
                self.insideLink = False
                return

            if not self.insideLink and self.insideResult and tag == self.DIV:
                self.insideResult = False
                return

            if not self.insideResult and self.insideResultContainer and tag == self.DIV:
                self.insideResultContainer = False
                return

            if not self.insideResultContainer and self.insideResultList and tag == self.DIV:
                self.insideResultList = False
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def get_search_url(self, what: str, page: int) -> str:
        return f'{self.url}/buscar/page/{page}?q={what}'

    def has_results(self, html: str) -> bool:
        no_results_matches = re.finditer(self.no_results_regex, html, re.MULTILINE)
        no_results = [x.group() for x in no_results_matches]
        return len(no_results) == 0

    def search(self, what: str, cat: str) -> None:
        should_continue = True
        what = what.replace('%20', '+')
        page = 1

        while should_continue:
            retrieved_html = retrieve_url(self.get_search_url(what,page), self.headers)

            if self.has_results(retrieved_html):
                parser = self.SearchResultsParser(self.url)
                parser.feed(retrieved_html)
                parser.close()

                page += 1
            else:
                should_continue = False
