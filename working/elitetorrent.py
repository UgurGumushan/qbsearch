#VERSION: 1.6
"""Elitetorrent (Spanish) engine: movie and TV series torrents.

The magnet link stored on each torrent page is obfuscated with repeated
Base64 plus ROT13 layers, which this engine reverses before printing.
"""
from __future__ import annotations

import base64
import codecs
import re
from datetime import datetime
from typing import ClassVar, TypedDict

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter

MAX_DEPTH = 10  # Safety cap on how many Base64+ROT13 layers to peel off.


class TorrentInfo(TypedDict):
    title: str | None
    link: list[str] | str | None
    size: str
    quality: str | None
    language: str | None
    date: str | int
    seeds: str | int
    leech: str | int
    formatted_name: str


def deobfuscate_magnet(obfuscated: str) -> str | None:
    encoded = obfuscated.encode()
    try:
        for _ in range(MAX_DEPTH):
            decoded_bytes = base64.b64decode(encoded)
            decoded_value = codecs.decode(decoded_bytes.decode(encoding='utf-8'), 'rot_13')
            if 'magnet' in decoded_value:
                return decoded_value
            encoded = decoded_bytes
    except Exception:
        return None
    return None


def format_info(info: TorrentInfo) -> None:
    links = info['link']
    if isinstance(links, list):
        # The site normally includes a second matching attribute; accept the
        # first one as a safe fallback when a page contains only one.
        encoded_link = links[1] if len(links) > 1 else links[0] if links else None
        info['link'] = (
            deobfuscate_magnet(encoded_link.lstrip('i=').rstrip('"'))
            if encoded_link is not None
            else None
        )
    else:
        info['link'] = None

    title = info['title'] or ''
    if title.startswith('<h1>') and title.endswith('</h1>'):
        title = title[4:-5]
    if title.startswith('Descargar ') and title.endswith(' por torrent'):
        title = title[10:-12].strip()

    formatted_name = title
    if info['language'] is not None:
        formatted_name += ' [{}]'.format(info['language'])
    if info['quality'] is not None:
        formatted_name += ' {} '.format(info['quality'])
    formatted_name += '({})'.format(info['date'])
    info['formatted_name'] = formatted_name

class elitetorrent:
    url = 'https://www.elitetorrent.com'
    name = 'Elitetorrent'
    # Page has only movies and tv series. Search box has no filters
    supported_categories: ClassVar[dict[str, str]]  = {'all': '0', 'movies': 'peliculas', 'tv': 'series'}

    def __init__(self) -> None:
        self.pages_limit = 2     # Limit of pages, more pages increase the time it takes

    def download_torrent(self, info: SearchResults) -> None:
        """Unused: results already carry ready-to-use magnet links."""
        print(download_file(info['link']))

    def search(self, what: str, cat: str = 'all') -> None:
        search_url = "{}/?s={}".format(self.url, what.replace('%20', '+'))
        html = retrieve_url(search_url)

        # Get number of pages
        number_pages = 0
        if "paginacion" in html:
            pages = re.findall(r'<a.*?class="pagina.*?</a>', html)
            if len(pages) > 0:
                last_page = pages[-1]
                last_page = re.findall(r'page/.*?/', last_page)[0]
                last_page = last_page.replace('/', '').replace('page', '')
                number_pages = int(last_page)

        # Only one page but there are results
        elif "Resultado de buscar" in html:
            number_pages = 1
        else:
            # No pagination links and no single-results banner: nothing found.
            number_pages = 0

        # Set number of pages depending by limit
        number_pages = min(self.pages_limit, number_pages)

        links: list[str] = []
        
        for page in range(1, number_pages + 1):
            # Page urls look like: {url}/page/{n}/?s={query}
            url = "{}/page/{}/?s={}".format(self.url, page, what.replace('%20', '+'))
            html = retrieve_url(url).replace('\n','')   # Replace newline to help the regex
            # I hate regex, check if selected category is films or tv, if its 'all' get both
            pattern = rf'({self.url}/series/.*?/|{self.url}/peliculas/.*?/)' if cat == "all" \
                        else rf'{self.url}/{self.supported_categories[cat]}/.*?/'
            # Collect every matching result link on the page.
            items = re.findall(pattern, html)
            for result_link in items:
                if result_link not in links:
                    links.append(result_link)

        for i in links:
            # Visiting individual results to get its attributes makes it so slow
            data = retrieve_url(i).replace('\n','')
            info: TorrentInfo = {
                'title': None,
                'link': [],
                'size': '0',
                'quality': None,
                'language': None,
                'date': -1,
                'seeds': -1,
                'leech': -1,
                'formatted_name': '',
            }
            m_title = re.search(r'<h1>Descargar .+ por torrent</h1>', data)
            info['title'] = m_title.group(0) if m_title else None
            info['link'] = re.findall(r'i=[-A-Za-z0-9+/]+\={0,3}\"', data)
            m = re.search(r"Tama.?o:</b> [0-9\.]+[\ GM]+B", data)
            info['size'] = m.group(0).split("</b>")[1].strip() if m else '0'
            m = re.search(r'Calidad:</b> [0-9\.a-z\-]+', data)
            info['quality'] = m.group(0).removeprefix('Calidad:</b>').strip() if m else None
            m = re.search(r'Idioma:</b>[a-zA-Zñ\ ]+', data)
            info['language'] = m.group(0).removeprefix('Idioma:</b>').strip() if m else None
            m = re.search(r'Fecha:</b>[\ 0-9\-]+', data)
            info['date'] = m.group(0).replace(' ', '').removeprefix('Fecha:</b>') if m else -1
            m = re.search(r'<b>Semillas</b>:[\ 0-9]*', data)
            info['seeds'] = m.group(0).split(":")[-1].strip() if m else -1
            m = re.search(r'<b>Clientes</b>:[\ 0-9]*', data)
            info['leech'] = m.group(0).split(":")[-1].strip() if m else -1

            format_info(info)
            if info['title'] is None or not isinstance(info['link'], str):
                continue    # decoding has failed, skip           

            pub_date = info['date']
            if isinstance(pub_date, str):
                # there are 2 format dates: YYYY-MM-DD or DD-MM-YYYY
                if int(pub_date.split("-")[0]) > 1000:
                    parsed_date = datetime.strptime(pub_date, "%Y-%m-%d")
                else:
                    parsed_date = datetime.strptime(pub_date, "%d-%m-%Y")
                pub_date = round(datetime.timestamp(parsed_date))

            seeds = info['seeds']
            leech = info['leech']
            item: SearchResults = {
                'seeds' : int(seeds) if isinstance(seeds, str) and seeds else seeds if isinstance(seeds, int) else -1,
                'leech' : int(leech) if isinstance(leech, str) and leech else leech if isinstance(leech, int) else -1,
                'name' : info['formatted_name'],
                'size' : info['size'],
                'desc_link' : i,
                'engine_url' : self.url,
                'link' : info['link'],
                'pub_date' : pub_date
            }
            # Prints in this format: link|name|size|seeds|leech|engine_url|desc_link|pub_date
            prettyPrinter(item)
