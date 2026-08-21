# VERSION: 1.2
"""DonTorrent engine: Spanish movies, series, anime and other torrents.

Search is submitted as a form POST; every card is followed to extract
its .torrent link and pages beyond the first run in parallel.
"""
from __future__ import annotations

import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter


class dontorrent:
    url = 'https://dontorrent.phd'
    headers: dict[str, str] = {  # noqa: RUF012
        'Referer': url
    }
    name = 'DonTorrent'
    supported_categories: ClassVar[dict[str, str]] = {
        'all': 'all'
    }
    
    results_regex = r'<p.+?>Se han encontrado.+?<b>\d+</b>.+?resultados.+?</p>'

    class MyHtmlParser(HTMLParser):
        magnet_regex = r'href=["\'].+?\.torrent["\']'
        size_regex = r'<p.+?><b.+?>Tamaño:</b>.+?</p>'

        def error(self, message: str) -> None:
            pass
    
        DIV, P, A, SPAN = ('div', 'p', 'a', 'span')
    
        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)

            self.url = url
            self.headers = {
                'Referer': url
            }
            self.row: SearchResults = {
                'link': '',
                'name': '',
                'size': '',
                'seeds': -1,
                'leech': -1,
                'engine_url': url,
            }

            self.column = 0

            self.insideBuscadorDiv = False
            self.insideCardDiv = False
            self.insideCardBodyDiv = False
            self.insideResult = False
            self.insideResultSpan = False
            self.insideLink = False
            self.insideType = False
            self.insideBadge = False

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            params = dict(attrs)
            cssClasses = params.get('class', '') or ''
            elementId = params.get('id', '')

            if tag == self.DIV and elementId == 'buscador':
                self.insideBuscadorDiv = True
                return

            if self.insideBuscadorDiv and 'card' in cssClasses and 'card-body' not in cssClasses:
                self.insideCardDiv = True
                return

            if self.insideCardDiv and 'card-body' in cssClasses:
                self.insideCardBodyDiv = True
                return

            if self.insideCardBodyDiv and tag == self.P and len(cssClasses) == 0:
                self.insideResult = True
                return

            if self.insideResult and not self.insideResultSpan and tag == self.SPAN:
                self.insideResultSpan = True
                return

            if self.insideResultSpan and tag == self.A:
                self.insideLink = True
                href = params.get('href') or ''
                link = f'{self.url}{href}'
                self.row['desc_link'] = link
                self.row['link'] = link
                torrent_page = retrieve_url(link, self.headers)
                matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                magnet_urls = [x.group() for x in matches]
                self.row['link'] = "https:" + magnet_urls[0].split("'")[1]
                matches = re.finditer(self.size_regex, torrent_page, re.MULTILINE)
                size = [x.group() for x in matches]
                sizeEl = re.sub(r'<b.+?>Tamaño:</b>', '', size[0])
                root = ET.fromstring(sizeEl)
                self.row['size'] = (root.text or '').replace(',', '.')
                self.row['seeds'] = -1
                self.row['leech'] = -1
                return

            if self.insideResultSpan and tag == self.SPAN and len(cssClasses) == 0:
                self.insideType = True
                return

            if self.insideResultSpan and tag == self.SPAN and 'badge' in cssClasses:
                self.insideBadge = True
                return

        def handle_data(self, data: str) -> None:
            if self.insideLink:
                self.row['name'] = data
                return

            if self.insideType:
                self.row['name'] += f" ({data})"
                return

            if self.insideBadge:
                self.row['name'] += f" [{data}]"
                return

        def handle_endtag(self, tag: str) -> None:
            if self.insideBadge and tag == self.SPAN:
                self.insideBadge = False
                return

            if self.insideType and tag == self.SPAN:
                self.insideType = False
                return

            if self.insideLink and tag == self.A:
                self.insideLink = False
                return

            if self.insideResultSpan and not self.insideBadge and not self.insideType and tag == self.SPAN:
                self.insideResultSpan = False
                return

            if self.insideResult and tag == self.P:
                self.row['engine_url'] = self.url
                prettyPrinter(self.row)
                self.column = 0
                self.row = {
                    'link': '',
                    'name': '',
                    'size': '',
                    'seeds': -1,
                    'leech': -1,
                    'engine_url': self.url,
                }
                self.insideResult = False
                self.insideResultSpan = False
                return

            if self.insideCardBodyDiv and tag == self.DIV:
                self.insideCardBodyDiv = False
                return

            if self.insideCardDiv and self.insideCardBodyDiv is False and tag == self.DIV:
                self.insideCardDiv = False
                return

            if self.insideBuscadorDiv and self.insideCardDiv is False and tag == self.DIV:
                self.insideBuscadorDiv = False
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def get_page_url(self):
        return f'{self.url}/buscar'

    def get_page_data(self, what: str, page: int) -> bytes:
        return f'valor={what}&Buscar=Buscar&p={page}'.encode()


    def threaded_search(self, page: int, what: str) -> None:
        page_url = self.get_page_url()
        self.headers['Referer'] = page_url
        retrieved_html = retrieve_url(page_url, self.headers, self.get_page_data(what, page))
        parser = self.MyHtmlParser(self.url)
        parser.feed(retrieved_html)
        parser.close()

    def search(self, what: str, cat: str = 'all') -> None:
        self.headers['Referer'] = self.get_page_url()
        page = 1
        retrieved_html = retrieve_url(self.get_page_url(), self.headers, self.get_page_data(what, page))
        matches = re.finditer(self.results_regex, retrieved_html, re.MULTILINE)
        results_el = [x.group() for x in matches]
        if len(results_el) > 0:
            root = ET.fromstring(results_el[0])
            results = root[0].text or '0'
            pages = math.ceil(int(results) / 10)

            parser = self.MyHtmlParser(self.url)
            parser.feed(retrieved_html)
            parser.close()

            page += 1

            threads = []
            while page <= pages:
                t = threading.Thread(args=(page, what), target=self.threaded_search)
                t.start()
                time.sleep(0.5)
                threads.append(t)

                page += 1

            for t in threads:
                t.join()
