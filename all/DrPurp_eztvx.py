#VERSION: 3.20
#AUTHORS: DrPurp (Updated)

import json
import re
from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter


class eztvx(object):
    url = 'https://eztvx.to'
    name = 'EZTVX'
    supported_categories = {
        'all': 'all',
        'tv': 'tv'
    }

    OMDB_API_KEY = 'YOUR_OMDB_API_KEY'  # Get a free key at https://www.omdbapi.com/apikey.aspx

    def __init__(self):
        pass

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat='all'):
        keywords = what.replace('%20', ' ').replace('.', ' ').replace('-', ' ')
        keywords = re.sub(r'\s+', ' ', keywords).strip()

        season, episode = self._parse_season_episode(keywords)
        title = self._clean_title(keywords)
        imdb_id = self._get_imdb_id(title)

        if imdb_id:
            self._search_by_imdb(imdb_id, season=season, episode=episode)
        else:
            self._search_by_keywords(title, season=season, episode=episode)

    def _parse_season_episode(self, keywords):
        pattern = re.compile(
            r'\b(?:'
            r's(\d{1,2})e(\d{1,2})'
            r'|s(\d{1,2})'
            r'|e(\d{1,2})'
            r'|(\d{1,2})x(\d{1,2})'
            r'|season\s*(\d{1,2})\s*episode\s*(\d{1,2})'
            r'|season\s*(\d{1,2})'
            r')\b', re.IGNORECASE
        )
        season, episode = None, None
        match = pattern.search(keywords)
        if match:
            g = match.groups()
            if g[0] and g[1]:
                season, episode = int(g[0]), int(g[1])
            elif g[2]:
                season = int(g[2])
            elif g[3]:
                episode = int(g[3])
            elif g[4] and g[5]:
                season, episode = int(g[4]), int(g[5])
            elif g[6] and g[7]:
                season, episode = int(g[6]), int(g[7])
            elif g[8]:
                season = int(g[8])
        return season, episode

    def _clean_title(self, keywords):
        episode_pattern = re.compile(
            r'\b(?:'
            r's(\d{1,2})e(\d{1,2})'
            r'|s(\d{1,2})'
            r'|e(\d{1,2})'
            r'|(\d{1,2})x(\d{1,2})'
            r'|season\s*(\d{1,2})\s*episode\s*(\d{1,2})'
            r'|season\s*(\d{1,2})'
            r')\b', re.IGNORECASE
        )
        junk_pattern = re.compile(
            r'\b(1080p|720p|480p|2160p|4k|x264|x265|hevc|avc|bluray|'
            r'webrip|web-dl|hdtv|dvdrip|proper|repack|extended|'
            r'theatrical|directors\.cut|remux)\b', re.IGNORECASE
        )
        cleaned = episode_pattern.sub('', keywords)
        cleaned = junk_pattern.sub('', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _matches_season_episode(self, title, season, episode):
        if season is None and episode is None:
            return True
        pattern = re.compile(
            r'\b(?:'
            r's(\d{1,2})e(\d{1,2})'
            r'|s(\d{1,2})'
            r'|e(\d{1,2})'
            r'|(\d{1,2})x(\d{1,2})'
            r'|season\s*(\d{1,2})\s*episode\s*(\d{1,2})'
            r'|season\s*(\d{1,2})'
            r')\b', re.IGNORECASE
        )
        s, e = None, None
        match = pattern.search(title)
        if match:
            g = match.groups()
            if g[0] and g[1]:
                s, e = int(g[0]), int(g[1])
            elif g[2]:
                s = int(g[2])
            elif g[3]:
                e = int(g[3])
            elif g[4] and g[5]:
                s, e = int(g[4]), int(g[5])
            elif g[6] and g[7]:
                s, e = int(g[6]), int(g[7])
            elif g[8]:
                s = int(g[8])
        if season is not None and episode is None:
            return s == season
        if episode is not None and season is None:
            return e == episode
        return s == season and e == episode

    def _get_imdb_id(self, title):
        if not title:
            return None
        try:
            omdb_url = (
                'http://www.omdbapi.com/?apikey={}&t={}&type=series'.format(
                    self.OMDB_API_KEY,
                    title.replace(' ', '+')
                )
            )
            response = retrieve_url(omdb_url)
            data = json.loads(response)
            if data.get('Response') == 'True':
                return data.get('imdbID', '').replace('tt', '')
        except Exception:
            pass
        return None

    def _search_by_imdb(self, imdb_id, season=None, episode=None):
        page = 1
        while True:
            api_url = '{}/api/get-torrents?limit=100&page={}&imdb_id={}'.format(
                self.url, page, imdb_id
            )
            try:
                response = retrieve_url(api_url)
                data = json.loads(response)
            except Exception:
                break

            torrents = data.get('torrents', [])
            if not torrents:
                break

            for torrent in torrents:
                title = torrent.get('title', '')
                if self._matches_season_episode(title, season, episode):
                    self._print_result(torrent)

            total = data.get('torrents_count', 0)
            if page * 100 >= int(total) or len(torrents) < 100:
                break
            page += 1

    def _search_by_keywords(self, keywords, season=None, episode=None):
        terms = [t.lower() for t in keywords.split() if t]
        page = 1

        while True:
            api_url = '{}/api/get-torrents?limit=100&page={}&Keywords={}'.format(
                self.url, page, keywords.replace(' ', '+')
            )
            try:
                response = retrieve_url(api_url)
                data = json.loads(response)
            except Exception:
                break

            torrents = data.get('torrents', [])
            if not torrents:
                break

            for torrent in torrents:
                title = torrent.get('title', '')
                title_lower = title.lower()
                if (all(term in title_lower for term in terms)
                        and self._matches_season_episode(title, season, episode)):
                    self._print_result(torrent)

            total = data.get('torrents_count', 0)
            if page * 100 >= int(total) or len(torrents) < 100:
                break
            page += 1

    def _print_result(self, torrent):
        link = torrent.get('magnet_url') or torrent.get('torrent_url', '')
        if not link:
            return
        result = {
            'link':       link,
            'name':       torrent.get('title', 'Unknown'),
            'size':       self._format_size(torrent.get('size_bytes', -1)),
            'seeds':      int(torrent.get('seeds', 0)),
            'leech':      int(torrent.get('peers', 0)),
            'engine_url': self.url,
            'desc_link':  torrent.get('episode_url', self.url),
        }
        prettyPrinter(result)

    def _format_size(self, size_bytes):
        try:
            size_bytes = int(size_bytes)
        except (TypeError, ValueError):
            return '-1'
        if size_bytes < 0:
            return '-1'
        elif size_bytes < 1024 ** 2:
            return '{:.1f} KB'.format(size_bytes / 1024)
        elif size_bytes < 1024 ** 3:
            return '{:.1f} MB'.format(size_bytes / (1024 ** 2))
        else:
            return '{:.2f} GB'.format(size_bytes / (1024 ** 3))