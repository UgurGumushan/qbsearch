# VERSION: 0.4


import urllib.parse
from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url
from novaprinter import prettyPrinter


class audiobookbay:
    url = 'http://theaudiobookbay.se/'
    urls: ClassVar[list[str]]  = [
        'http://theaudiobookbay.se/',
        'http://audiobookbay.fi/',
        'http://audiobookbay.is/'
    ]

    name = 'AudioBook Bay (ABB)'
    supported_categories: ClassVar[dict[str, str]] = {'all': 'all'}

    class TorrentInfoParser(HTMLParser):

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url
            self.foundArchiveTitle = False
            self.parseArchiveTitle = False
            self.foundResult = False
            self.foundTitle = False
            self.parseTitle = False
            self.torrentReady = False
            self.totalPages = 0
            self.torrent_info = self.empty_torrent_info()

        def empty_torrent_info(self):
            return {
                'link': '',
                'name': '',
                'size': '100 MB',
                'seeds': '1',
                'leech': '1',
                'engine_url': self.url,
                'desc_link': ''
            }

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)

            if 'archiveTitle' in params.get('class', ''):
                self.foundArchiveTitle = True

            if (self.foundArchiveTitle and tag == 'h3'):
                self.parseArchiveTitle = True

            if 'post' in params.get('class', ''):
                self.foundResult = True

            if (self.foundResult and 'postTitle' in params.get('class', '')):
                self.foundTitle = True

            if (self.foundTitle and tag == 'a'):
                self.torrent_info['desc_link'] = self.url + params.get('href')
                self.parseTitle = True

            if (tag == 'a' and '»»' in params.get('title', '')):
                self.totalPages = int(params.get('href').split('/')[2])

        def handle_endtag(self, tag):
            if (self.torrentReady):
                size, magnet = self.fetchTorrentDetails(self.torrent_info['name'], self.torrent_info['desc_link'])
                self.torrent_info['link'] = magnet
                if (bool(size)):
                    self.torrent_info['size'] = size

                prettyPrinter(self.torrent_info)
                self.torrent_info = self.empty_torrent_info()
                self.foundResult = False
                self.torrentReady = False

        def handle_data(self, data):

            if (self.parseTitle):
                if (bool(data.strip()) and data != '\n'):
                    self.torrent_info['name'] = data
                self.parseTitle = False
                self.foundTitle = False
                self.torrentReady = True

            if (self.parseArchiveTitle):
                self.parseArchiveTitle = False
                self.foundArchiveTitle = False
                if (data == 'Not Found'):
                    raise Exception('Not Found')

        class TorrentPageParser(HTMLParser):

            def __init__(self):
                HTMLParser.__init__(self)
                self.hash = ''
                self.size = ''
                self.parseFileSize = False
                self.parseHash = False

            def handle_data(self, data):
                if (data.strip() == 'Info Hash:'):
                    self.parseHash = True
                    return

                if (self.parseHash) and (bool(data.strip())):
                    self.hash = data.strip()
                    self.parseHash = False
                    return

                if (data.strip() == 'Combined File Size:'):
                    self.parseFileSize = True
                    return

                if (self.parseFileSize) and (bool(data.strip())):

                    if (bool(self.size)):
                        self.size = self.size + data.replace('s', '')
                        self.parseFileSize = False
                        return
                    self.size = data

        def fetchTorrentDetails(self, title, url):
            html = retrieve_url(url)
            parser = self.TorrentPageParser()
            parser.feed(html)

            link = "magnet:" \
                   + "?xt=urn:btih:" + parser.hash \
                   + "&dn=" + urllib.parse.quote(title) \
                   + "&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969" \
                   + "&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969" \
                   + "&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce" \
                   + "&tr=udp%3A%2F%2Ftracker.open-internet.nl%3A6969%2Fannounce" \
                   + "&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A69691337%2Fannounce" \
                   + "&tr=udp%3A%2F%2Ftracker.vanitycore.co%3A6969%2Fannounce" \
                   + "&tr=http%3A%2F%2Ftracker.baravik.org%3A6970%2Fannounce" \
                   + "&tr=http%3A%2F%2Fretracker.telecom.by%3A80%2Fannounce" \
                   + "&tr=http%3A%2F%2Ftracker.vanitycore.co%3A6969%2Fannounce"

            parser.close()

            return parser.size, link

    def find_healthy_url(self):
        """Checks multiple URLs in sequence and returns the first one that works."""
        for url in self.urls:
            response = retrieve_url(url)
            if response:
                return url

        return None

    def request(self, url, searchTerm, category, page=1):
        request_url = url + '/page/' + str(page) + '/?s=' + searchTerm + '&cat=' + category
        return retrieve_url(request_url)

    def search(self, what, cat='all'):
        category = self.supported_categories[cat]

        url = self.find_healthy_url()

        if not url:
            print("No healthy url found!")
            return ""

        parser = self.TorrentInfoParser(url)

        try:
            parser.feed(self.request(url, what, category, 1))
            totalPages = parser.totalPages
            for page in range(2, totalPages + 1):
                parser.feed(self.request(url, what, category, page))
        finally:
            parser.close()