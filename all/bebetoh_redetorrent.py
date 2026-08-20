# VERSION: 1.00
# AUTHORS: bebetoh
# https://redetorrent.com
# pt_BR
# Conteúdo com Audio em Português (Dublado / Dual Áudio / Legendado)

import html
import re
import sys
from html.parser import HTMLParser
from typing import Dict, List, Mapping, Tuple, Union
from urllib.parse import quote_plus, unquote, urljoin

from helpers import retrieve_url
from novaprinter import prettyPrinter


class redetorrent:
    url = 'https://redetorrent.com'
    name = 'RedeTorrent'
    supported_categories = {
        'all': 'all',
        'anime': 'desenhos',
        'movies': 'filmes',
        'tv': 'series',
    }

    class SearchResultsParser(HTMLParser):
        def __init__(self, base_url: str) -> None:
            HTMLParser.__init__(self)
            self.base_url = base_url
            self.results: List[Dict[str, str]] = []

            self.inside_card = False
            self.div_depth = 0
            self.inside_headline = False
            self.current_link = ''
            self.current_title = ''

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == 'div':
                if 'capa_lista' in self._get(params, 'class'):
                    self.inside_card = True
                    self.div_depth = 1
                    self.current_link = ''
                    self.current_title = ''
                elif self.inside_card:
                    self.div_depth += 1
                return

            if not self.inside_card:
                return

            if tag == 'a':
                href = self._get(params, 'href')
                if href and not self.current_link:
                    self.current_link = urljoin(self.base_url, href)

            if tag == 'h2' and self._get(params, 'itemprop') == 'headline':
                self.inside_headline = True

        def handle_data(self, data: str) -> None:
            if self.inside_card and self.inside_headline:
                text = self._clean_text(data)

                if text:
                    if self.current_title:
                        self.current_title += ' '
                    self.current_title += text

        def handle_endtag(self, tag: str) -> None:
            if tag == 'h2' and self.inside_headline:
                self.inside_headline = False

            if tag == 'div' and self.inside_card:
                self.div_depth -= 1
                if self.div_depth <= 0:
                    title = self._clean_title(self.current_title)

                    if self.current_link and title:
                        self.results.append({
                            'title': title,
                            'desc_link': self.current_link,
                        })

                    self.inside_card = False
                    self.div_depth = 0
                    self.current_link = ''
                    self.current_title = ''

        def _attrs_to_dict(self, attrs: List[Tuple[str, Union[str, None]]]) -> Dict[str, str]:
            result = {}

            for key, value in attrs:
                result[key] = value if value is not None else ''

            return result

        def _get(self, params: Mapping[str, str], key: str) -> str:
            return params.get(key, '')

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = re.sub(r'\s*Download\s*$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s+', ' ', title)
            return title.strip()

    class MagnetLinksParser(HTMLParser):
        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.magnets: List[Dict[str, str]] = []
            self.inside_download_area = False

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == 'p' and params.get('id') == 'lista_download':
                self.inside_download_area = True
                return

            if not self.inside_download_area:
                return

            if tag == 'a':
                href = params.get('href', '')
                title = params.get('title', '')

                if href.startswith('magnet:?'):
                    self.magnets.append({
                        'magnet': html.unescape(href),
                        'title': self._clean_title(title),
                    })

        def handle_endtag(self, tag: str) -> None:
            if tag == 'p' and self.inside_download_area:
                self.inside_download_area = False

        def _attrs_to_dict(self, attrs: List[Tuple[str, Union[str, None]]]) -> Dict[str, str]:
            result = {}

            for key, value in attrs:
                result[key] = value if value is not None else ''

            return result

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = re.sub(r'^DOWNLOAD\s+', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s+', ' ', title)
            return title.strip()

    def search(self, what: str, cat: str = 'all') -> None:
        search_url = self._build_search_url(what, cat)

        try:
            search_html = retrieve_url(search_url)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f'Rede Torrent search request failed: {exc}', file=sys.stderr)
            return

        search_parser = self.SearchResultsParser(self.url)
        search_parser.feed(search_html)
        search_parser.close()

        for result in search_parser.results:
            self._print_result_magnets(result)

    def _build_search_url(self, what: str, cat: str) -> str:
        query = what.replace('%20', '+')

        if cat not in self.supported_categories:
            cat = 'all'

        return self.url + '/index.php?s=' + quote_plus(query).replace('%2B', '+')

    def _print_result_magnets(self, result: Dict[str, str]) -> None:
        desc_link = result.get('desc_link', '')
        base_title = result.get('title', '').strip()

        if not desc_link:
            return

        try:
            details_html = retrieve_url(desc_link)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f'Rede Torrent details request failed: {exc}', file=sys.stderr)
            return

        magnet_parser = self.MagnetLinksParser()
        magnet_parser.feed(details_html)
        magnet_parser.close()

        for magnet_item in magnet_parser.magnets:
            magnet = magnet_item.get('magnet', '')
            magnet_title = magnet_item.get('title', '')

            if not magnet:
                continue

            name = self._build_result_name(base_title, magnet_title, magnet)

            torrent_info = {
                'link': magnet,
                'name': name,
                'size': '-1',
                'seeds': -1,
                'leech': -1,
                'engine_url': self.url,
                'desc_link': desc_link,
                'pub_date': -1,
            }

            prettyPrinter(torrent_info)  # type: ignore[arg-type]

    def _build_result_name(self, base_title: str, magnet_title: str, magnet: str) -> str:
        if magnet_title:
            return base_title + ' - ' + magnet_title

        magnet_name = self._extract_magnet_dn(magnet)

        if magnet_name:
            return base_title + ' - ' + magnet_name

        return base_title

    def _extract_magnet_dn(self, magnet: str) -> str:
        match = re.search(r'[?&]dn=([^&]+)', magnet)

        if not match:
            return ''

        name = unquote(match.group(1))
        name = name.replace('.', ' ')
        name = re.sub(r'\s+', ' ', name)

        return name.strip()
