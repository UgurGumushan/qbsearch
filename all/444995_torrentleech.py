# VERSION: 1.0
# AUTHOR: github.com/444995

import os
import json
import gzip
import urllib.parse
import urllib.request
import tempfile
import http.cookiejar as cookielib
from urllib.error import HTTPError
from novaprinter import prettyPrinter
from math import ceil

# User settings
USERNAME = "REPLACE_ME"
PASSWORD = "REPLACE_ME"
CACHE_LOGIN_COOKIES = True
COOKIES_FILE_NAME = "torrentleech.cookies"

class torrentleech(object):
    url = 'https://www.torrentleech.org'
    name = 'TorrentLeech'
    supported_categories = {
        'all': '0', 
        'anime': '34',
        'movies': '8,9,11,37,43,14,12,13,47,15,29', 
        'tv': '26,32,27', 
        'music': '31,16',
        'games': '17,42,18,19,40,20,21,39,49,22,28,30,48', 
        'software': '23,24,25,33', 
        'books': '45,46',
    }
    cookies_file_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 
        COOKIES_FILE_NAME
    )

    def __init__(self):
        self.login_url = f"{self.url}/user/account/login/"
        self.torrents_per_page = 50
        self.cookiejar = cookielib.LWPCookieJar()
        self.opener = self._create_opener()
        self._login()

    def _create_opener(self):
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookiejar))
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0'),
            ('Accept-Encoding', 'gzip, deflate'),
        ]
        return opener

    def _make_request(self, url, data=None):
        try:
            encoded_data = urllib.parse.urlencode(data).encode() if data else None
            with self.opener.open(url, encoded_data) as response:
                if response.info().get('Content-Encoding') == 'gzip':
                    return gzip.decompress(response.read())
                return response.read()
        except HTTPError as e:
            raise Exception(f"Request failed: {e}")

    def _login(self):
        if CACHE_LOGIN_COOKIES and os.path.exists(self.cookies_file_path):
            self.cookiejar.load(self.cookies_file_path, ignore_discard=True, ignore_expires=True)
            if self._is_logged_in():
                return

        data = {"username": USERNAME, 
                "password": PASSWORD}
        self._make_request(self.login_url, data)

        if not self._is_logged_in():
            raise ValueError("Failed to login: Invalid credentials")

        if CACHE_LOGIN_COOKIES:
            self.cookiejar.save(self.cookies_file_path, ignore_discard=True, ignore_expires=True)

    def _is_logged_in(self):
        return any(cookie.name == 'tlpass' for cookie in self.cookiejar)

    def download_torrent(self, info):
        torrent_file = self._make_request(info)
        with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as file:
            file.write(torrent_file)
        print(f"{file.name} {info}")


    def search(self, what, cat='all'):
        category_str = self.supported_categories[cat]
        search_url = self._establish_search_url(what, category_str)
        
        total_pages = self._get_total_pages(search_url)
        for page in range(1, total_pages + 1):
            self._search_page(f"{search_url}/page/{page}")

    def _establish_search_url(self, what, category_str):
        base_url = f"{self.url}/torrents/browse/list"
        return f"{base_url}/categories/{category_str}/query/{what}" if category_str != '0' else f"{base_url}/query/{what}"

    def _get_total_pages(self, search_url):
        response = self._make_request(f"{search_url}/page/1")
        num_torrents = json.loads(response).get("numFound", 0)
        return ceil(num_torrents / self.torrents_per_page)

    def _search_page(self, url):
        response = self._make_request(url)
        torrents = json.loads(response).get("torrentList", [])
        for torrent in torrents:
            self._print_torrent(torrent)

    def _print_torrent(self, torrent):
        prettyPrinter({
            'link': f"{self.url}/download/{torrent['fid']}/{torrent['filename']}",
            'name': torrent['name'],
            'size': f"{torrent['size']} B",
            'seeds': torrent['seeders'],
            'leech': torrent['leechers'],
            'engine_url': self.url,
            'desc_link': f"{self.url}/torrent/{torrent['fid']}"
        })

if __name__ == "__main__":
    engine = torrentleech()
    engine.search("ubuntu")
