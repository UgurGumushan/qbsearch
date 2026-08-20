# VERSION: 1.2
# AUTHOR: RaresPNet

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from novaprinter import prettyPrinter  # type: ignore

USERNAME = "YOUR_USERNAME"
PASSKEY  = "YOUR_PASSKEY"

class filelist(object):
    url  = 'https://filelist.io'
    name = 'FileList'
    supported_categories = {
        'all':      '0',
        'movies':   '1,2,3,4,19,20,26',
        'tv':       '5,6,7,8,22,23',
        'music':    '11',
        'games':    '9,10',
        'software': '15,16',
        'anime':    '24',
        'books':    '18',
    }

    API_URL = 'https://filelist.io/api.php'

    def download_torrent(self, info):
        from helpers import download_file
        print(download_file(info))

    def search(self, what, cat='all'):
        category = self.supported_categories.get(cat, '0')
        query = urllib.parse.quote_plus(what.replace('%20', ' '))

        cat_ids = category.split(',')

        seen = set()
        for cat_id in cat_ids:
            page = 0
            while True:
                params = urllib.parse.urlencode({
                    'username': USERNAME,
                    'passkey':  PASSKEY,
                    'action':   'search-torrents',
                    'type':     'name',
                    'query':    query,
                    'cat':      cat_id,
                    'page':     page,
                })
                req = urllib.request.Request(
                    f'{self.API_URL}?{params}',
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                try:
                    with urllib.request.urlopen(req) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                except Exception:
                    break

                if not data:
                    break

                for torrent in data:
                    tid = torrent.get('id')
                    if tid in seen:
                        continue
                    seen.add(tid)

                    category = torrent.get('category', '')
                    name = f"[{category}] " + torrent.get('name', 'N/A') if category else torrent.get('name', 'N/A')
                    if torrent.get('freeleech'):
                        name += ' [FreeLeech]'
                    if torrent.get('doubleup'):
                        name += ' [2x]'

                    upload_date = torrent.get('upload_date', '')
                    try:
                        pub_date = int(datetime.strptime(upload_date, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
                    except (ValueError, TypeError):
                        pub_date = ''

                    prettyPrinter({
                        'name':       name,
                        'size':       str(torrent.get('size', -1)),
                        'seeds':      torrent.get('seeders', 0),
                        'leech':      torrent.get('leechers', 0),
                        'engine_url': self.url,
                        'desc_link':  f'{self.url}/details.php?id={tid}',
                        'link':       torrent.get('download_link') or f'{self.url}/download.php?id={tid}&passkey={PASSKEY}',
                        'pub_date':   pub_date,
                    })

                if len(data) < 100:
                    break
                page += 1
