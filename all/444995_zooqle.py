# VERSION: 1.1
# AUTHORS: github.com/444995
# Not the best code I've written, will prob get updated

import re
import gzip
import tempfile
import urllib.parse
from urllib.error import HTTPError
import http.cookiejar as cookielib
from novaprinter import prettyPrinter

# EVEN IF THIS IS SET TO FALSE
# IT STILL FALLS BACK TO MAGNET LINKS 
# IF A TORRENT FILE IS NOT AVAILABLE
USE_MAGNET_LINKS = False # FALSE IS RECOMMENDED

class zooqle(object):
    url = 'https://zooqle.skin'
    name = 'Zooqle'

    supported_categories = {
        'all': '0', 
        'anime': 'anime',
        'movies': 'movies', 
        'tv': 'tv', 
        'music': 'music',
        'games': 'games', 
        'software': 'apps',
        'books': None,
    }
    search_url = f"{url}/search/"
    download_url = f"{url}/torfile/"
    torrent_page_url = f'{url}/torrent-page/'

    PATTERNS = {
        'category': r'<li><a href="javascript:void\(\);" onclick="p([^"]+)\.submit\(\)" style="[^"]*">([^<]+)</a></li>',
        'row': r'<tr>.*?</tr>',
        'torrent_id': r'<input type="hidden" name="id" value="(\d+)"',
        'name': r'<title>(.*?)\s+Torrent - Zooqle</title>',
        'size': r'<i class="fa fa-file"></i>\s*&nbsp;\s*<strong>Size</strong>.*?</li>\s*<li>:</li>\s*<li>(.*?)</li>',
        'seeds': r'<i class="fa fa-arrow-up"></i>\s*&nbsp;\s*<strong>Seed</strong>.*?</li>\s*<li>:</li>\s*<li[^>]*>(.*?)</li>',
        'leech': r'<i class="fa fa-arrow-down"></i>\s*&nbsp;\s*<strong>Leech</strong>.*?</li>\s*<li>:</li>\s*<li[^>]*>(.*?)</li>',
        'category_match': r'<i class="fa fa-tag"></i>\s*&nbsp;\s*<strong>Category</strong>.*?</li>\s*<li>:</li>\s*<li><a[^>]*>([^<]+)</a>',
        'magnet_link': r'href="(magnet:\?xt=urn:btih:[^"]+)"',
        'hid': r'<input type="hidden" name="hid" value="([^"]+)"'
    }

    def __init__(self):
        self.torrents_per_page = 40
        self.cookiejar = cookielib.LWPCookieJar()
        self.opener = self._create_opener()

    def _create_opener(self):
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookiejar))
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'),
            ('Content-Type', 'application/x-www-form-urlencoded'),
        ]
        return opener


    def _make_request(self, url, data=None, extra_headers=None):
        try:
            encoded_data = urllib.parse.urlencode(data).encode() if data else None
            request = urllib.request.Request(url, encoded_data)
            
            if extra_headers:
                for key, value in extra_headers.items():
                    request.add_header(key, value)
            
            with self.opener.open(request) as response:
                if response.info().get('Content-Encoding') == 'gzip':
                    content = gzip.decompress(response.read())
                else:
                    content = response.read()
                
                return content
            
        except HTTPError as e:
            raise HTTPError(f"Request failed: {e}")

    def download_torrent(self, info):
        if USE_MAGNET_LINKS:
            return
        
        torrent_file = self._make_request(
            url=self.download_url, 
            data={"hid": info}
        )
        
        with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as file:
            file.write(torrent_file)

        print(f"{file.name} {self.download_url}")

    def search(self, what, cat='all'):
        formatted_what = what.replace(" ", "+")
        category = self._establish_category_url(cat)
        
        page_num = 1
        while True:
            response = self._make_request(
                url=f"{self.url}/query/{formatted_what}/page/{page_num}",
                data={'q': what,
                      'page': page_num},
                extra_headers={
                    "referer": f'https://zooqle.skin/category/{category}/'
                } if category != '0' else {},
            ).decode('utf-8', errors='ignore')

            num_results = self._parse_results(response, category)

            if num_results < self.torrents_per_page:
                return
            
            page_num += 1
    
    def _establish_category_url(self, category):
        return self.supported_categories[category]

    def _parse_results(self, html_content, category):
        rows = re.findall(self.PATTERNS['row'], html_content, re.DOTALL)
        
        torrents_found = 0
        for row in rows:
            torrent_id = self._get_torrent_id(row)
            if torrent_id is None:
                continue
            torrent_page = self._get_torrent_page(torrent_id)
            torrent_data = self._extract_torrent_data(torrent_page, category)
            if torrent_data:
                prettyPrinter(torrent_data)
                print("\n\n")
                torrents_found += 1

        return torrents_found
    
    def _extract_torrent_data(self, torrent_page, category):
        name_elem = re.search(self.PATTERNS['name'], torrent_page, re.DOTALL)
        name = name_elem.group(1).strip() if name_elem else "N/A"

        size_elem = re.search(self.PATTERNS['size'], torrent_page, re.DOTALL)
        size = size_elem.group(1).strip() if size_elem else "N/A"

        seeds_elem = re.search(self.PATTERNS['seeds'], torrent_page, re.DOTALL)
        seeds = seeds_elem.group(1).strip() if seeds_elem else -1

        leech_elem = re.search(self.PATTERNS['leech'], torrent_page, re.DOTALL)
        leech = leech_elem.group(1).strip() if leech_elem else -1

        if category != '0':
            category_match = re.search(self.PATTERNS['category_match'], torrent_page, re.DOTALL).group(1).strip()

            if category_match.lower() != category:
                return None

        return {
            'name': name,
            'size': size,
            'seeds': int(seeds) if str(seeds).isdigit() else -1,
            'leech': int(leech) if str(leech).isdigit() else -1,
            'link': self._get_download_link(torrent_page),
            'desc_link': self.url,
            'engine_url': self.url,
        }

    def _get_torrent_id(self, row):
        match = re.search(self.PATTERNS['torrent_id'], row)
        return match.group(1) if match else None

    def _get_torrent_page(self, torrent_id):
        return self._make_request(
            self.torrent_page_url, 
            data={'id': torrent_id}, 
        ).decode('utf-8', errors='ignore')

    def _get_download_link(self, torrent_page):
        magnet_link = None
        hid = None

        magnet_match = re.search(self.PATTERNS['magnet_link'], torrent_page)
        if magnet_match:
            magnet_link = magnet_match.group(1)

        if not USE_MAGNET_LINKS:
            hid_match = re.search(self.PATTERNS['hid'], torrent_page)
            if hid_match:
                hid = hid_match.group(1)

        if USE_MAGNET_LINKS or (not USE_MAGNET_LINKS and not hid):
            return magnet_link if magnet_link else 'N/A'
        else:
            return hid
        
if __name__ == "__main__":
    engine = zooqle()
    engine.search("1080p", "all")
