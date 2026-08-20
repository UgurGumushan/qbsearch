# VERSION: 1.50
# AUTHOR: github.com/444995
# WILL GET UPDATED IF BROKEN

# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.                 

# USER SETTINGS
PRIVATE_USERNAME = "REPLACE_ME"           # A DANISHBYTES ACCOUNT HAS A PRIVATE USERNAME
PUBLIC_USERNAME = "REPLACE_ME"            # AND A PUBLIC USERNAME
PASSWORD = "REPLACE_ME"                   # YOU ALSO NEED A PASSWORD
CACHE_LOGIN_COOKIES = True                # CACHE COOKIES (HIGHLY RECOMMENDED)
COOKIES_FILE_NAME = "danishbytes.cookies" # THE PATH TO THE LOGIN
USE_MAGNET_URLS = False                   # USES MAGNET LINKS OR TORRENT FILES DEPENDING ON TRUE/FALSE (FALSE IS RECOMMENDED)

# IMPORTS
import os
import re
import json
import gzip
import tempfile
import urllib.parse
import urllib.request
import http.cookiejar as cookielib
from urllib.error import HTTPError
from novaprinter import prettyPrinter


class HtmlExtractor:
    """
    Extracts needed keys and tokens from a given HTML response.
    """
    @staticmethod
    def extract_meta_content(html, name):
        """Extracts content from meta tag with the given name."""
        pattern = r'<meta\s+[^>]*name=["\']{}["\'][^>]*>'.format(re.escape(name))
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            tag = match.group()
            content_match = re.search(r'content=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if content_match:
                return content_match.group(1).strip()
        return None

    @staticmethod
    def extract_input_value(html, name):
        """Extracts value from input tag with the given name."""
        pattern = r'<input\s+[^>]*name=["\']{}["\'][^>]*>'.format(re.escape(name))
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            tag = match.group()
            value_match = re.search(r'value=["\']([^"\']*)["\']', tag, re.IGNORECASE)
            if value_match:
                return value_match.group(1).strip()
        return None

    @staticmethod
    def extract_attr(html, attr_name, num=-1):
        """Extracts the attribute value from the input tag with the given number."""
        inputs = re.findall(r'<input\s+[^>]*>', html, re.IGNORECASE)
        if inputs:
            if num == -1:
                input_tag = inputs[-1]
            else:
                if num < len(inputs):
                    input_tag = inputs[num]
                else:
                    return None
            attr_match = re.search(r'{}=["\']([^"\']+)["\']'.format(re.escape(attr_name)), input_tag, re.IGNORECASE)
            if attr_match:
                return attr_match.group(1).strip()
        return None

class danishbytes(object):
    """
    DanishBytes engine for qBittorrent.
    """
    name = 'DanishBytes'
    url = 'https://danishbytes.club'
    login_url = f"{url}/login"
    tracker_urls = [
        "https://danishbytes2.org/announce", 
        "https://dbytes.org/announce", 
        "https://danishbytes.club/announce"
    ]
    categories_string = "&categories%5B%5D="
    user_agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0'

    supported_categories = {
        'all': '0', # 'all' is just every category combined
        'movies': '1',
        'tv': '2',
        'music': '3',
        'games': '4',
        'software': '5',
        'books': '8',
    }

    def __init__(self):
        """
        Initializes the DanishBytes engine for qBittorrent.
        """
        self.cookies_file_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 
            COOKIES_FILE_NAME
        )
        self.html_extractor = HtmlExtractor()
        self.cookiejar = cookielib.LWPCookieJar(self.cookies_file_path)
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookiejar))
        self.opener.addheaders = [
            ('User-Agent', self.user_agent),
            ('Accept-Encoding', 'gzip, deflate'),
        ]

        if CACHE_LOGIN_COOKIES and os.path.exists(self.cookies_file_path):
            self.cookiejar.load(
                self.cookies_file_path,
                ignore_discard=True,
                ignore_expires=True
            )
        else:
            self._login()

        self._set_csrf_token()

    def _login(self):
        """
        Logs into DanishBytes; this automatically sets the cookies in the cookiejar
        when self.opener is used hence why cookies aren't returned
        """
        # initial request to get cookies and keys
        response = self._make_request(self.login_url)
        html = response
        
        payload = { 
            "_token": self.html_extractor.extract_meta_content(html, "csrf-token"),
            "private_username": PRIVATE_USERNAME,
            "username": PUBLIC_USERNAME,
            "password": PASSWORD,
            "remember": "on",
            "_captcha": self.html_extractor.extract_input_value(html, "_captcha"),
            "_username": self.html_extractor.extract_input_value(html, "_username"),
            self.html_extractor.extract_attr(html, "name"): self.html_extractor.extract_attr(html, "value")
        }
        
        try:
            self._make_request(self.login_url, data=payload)
        except HTTPError as e:
            raise Exception(f"Login failed with error code: {e.code}") from e

        if CACHE_LOGIN_COOKIES:
            self.cookiejar.save(
                self.cookies_file_path, 
                ignore_discard=True, 
                ignore_expires=True
            )
    
    def download_torrent(self, info):
        """
        Downloads the torrent file
        """
        torrent_file = self._make_request(info)
        with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as _file:
            _file.write(torrent_file.encode('utf-8'))
        
        print(f"{_file.name} {info}")

    def search(self, what, cat='all'):
        """
        Searches for torrents on DanishBytes.
        """
        category_param = self._get_category_param(cat)
        page_num = 1

        while True:
            torrent_count = self._search_page(what, page_num, category_param)
            if torrent_count < 100:
                break
            page_num += 1

    def _get_category_param(self, cat):
        """
        Constructs the category parameter string for the search URL.
        """
        if cat == 'all':
            return ''.join([self.categories_string + c for c in self.supported_categories.values()])
        return self.categories_string + self.supported_categories[cat]

    def _search_page(self, what, page_num, category_param):
        """
        Handles a single page of search results.
        """
        search_url = f"{self.url}/torrents/filter?_token={self.csrf_token}&search={what}&page={page_num}&qty=100{category_param}"
        response = self._make_request(search_url)
        search_results = json.loads(response)

        for torrent in search_results['torrents']:
            self._print_torrent(torrent, search_results['rsskey'], search_results['passkey'])

        return len(search_results['torrents'])

    def _make_request(self, url, data=None):
        """
        Makes a request to the given URL using urllib.
        """
        encoded_data = urllib.parse.urlencode(data).encode() if data else None
        with self.opener.open(url, encoded_data or None) as response:
            content = gzip.GzipFile(fileobj=response).read() if response.info().get('Content-Encoding') == 'gzip' else response.read()
            return content.decode('utf-8', errors='replace')

    def _print_torrent(self, torrent, rss_key, pass_key):
        """
        Prints a single torrent's details.
        """
        _link = self._make_magnet_url(torrent, rss_key, pass_key) if USE_MAGNET_URLS else f"{self.url}/torrents/download/{torrent['id']}"
        prettyPrinter({
            'link': _link,
            'name': torrent['name'],
            'size': f"{str(torrent['size'])} B",
            'seeds': torrent['seeders'],
            'leech': torrent['leechers'],
            'engine_url': self.url,
            'desc_link': f"{self.url}/torrents/{torrent['id']}"
        })

    def _make_magnet_url(self, torrent, rss_key, pass_key):
        """
        Constructs the magnet URL for a torrent.
        """
        magnet_url = "magnet:?"
        magnet_url += f"dn={urllib.parse.quote(torrent['name'])}&"
        magnet_url += f"xt=urn:btih:{torrent['info_hash']}&"
        magnet_url += f"as={self.url}/torrent/download/{torrent['id']}.{rss_key}&"
        magnet_url += f"xl={torrent['size']}&"
        for tracker in self.tracker_urls:
            magnet_url += f"tr={urllib.parse.quote(tracker)}/{pass_key}&"
        return magnet_url.rstrip('&')

    def _set_csrf_token(self):
        """
        Sets the CSRF token for the current session, so it can be used for search requests.
        """
        response = self._make_request(self.url)
        html = response
        self.csrf_token = self.html_extractor.extract_meta_content(html, "csrf-token")


if __name__ == "__main__":
    # For testing purposes
    db = danishbytes()
    db.search("hello", "all")
    db.download_torrent("https://danishbytes.club/torrents/download/25600")
