#VERSION: 1.22
#AUTHORS: anon
from html.parser import HTMLParser

from helpers import retrieve_url, download_file
from novaprinter import prettyPrinter


class pantsu(object):
    url = 'https://nyaa.net'
    name = 'pantsu'
    supported_categories = {'all': '_',
                            'anime': '3_',
                            'books': '4_',
                            'music': '2_',
                            'pictures': '6_',
                            'software': '1_',
                            'games': '1_2'}
    engine_url = 'pantsu'

    class SearchResultsParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.results = []
            self.inside_row = False
            self.row = {}
            self.in_name = False
            self.in_size = False
            self.in_seeds = False
            self.in_leech = False

        def handle_starttag(self, tag, attrs):
            params = {}
            for key, value in attrs:
                params[key] = value if value is not None else ''
            if tag == 'tr':
                self.inside_row = True
                self.row = {'seeds': -1, 'leech': -1}
                return
            if not self.inside_row:
                return
            if tag == 'td':
                css = params.get('class', '')
                if 'col-name' in css:
                    self.in_name = True
                elif 'col-size' in css:
                    self.in_size = True
                elif 'num-s' in css:
                    self.in_seeds = True
                elif 'num-l' in css:
                    self.in_leech = True
            elif tag == 'a':
                href = params.get('href', '')
                if self.in_name and href.startswith('/view/'):
                    self.row['name'] = params.get('title', '')
                    self.row['desc_link'] = 'https://nyaa.net' + href
                elif href.startswith('magnet:?'):
                    self.row['link'] = href

        def handle_data(self, data):
            if self.in_size:
                self.row['size'] = data.strip()
                self.in_size = False
            elif self.in_seeds:
                try:
                    self.row['seeds'] = int(data.strip())
                except ValueError:
                    self.row['seeds'] = -1
                self.in_seeds = False
            elif self.in_leech:
                try:
                    self.row['leech'] = int(data.strip())
                except ValueError:
                    self.row['leech'] = -1
                self.in_leech = False

        def handle_endtag(self, tag):
            if tag == 'td':
                self.in_name = False
            elif tag == 'tr' and self.inside_row:
                if 'link' in self.row and self.row.get('name'):
                    self.row['engine_url'] = 'pantsu'
                    self.results.append(self.row)
                self.inside_row = False
                self.row = {}

    def __init__(self):
        pass

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat='all'):
        cat_code = self.supported_categories.get(cat, '_')
        if cat_code == '_':
            url = self.url + '/?f=0&q=' + what
        else:
            url = self.url + '/?f=0&c=' + cat_code + '&q=' + what

        parser = self.SearchResultsParser()
        parser.feed(retrieve_url(url))
        parser.close()

        for row in parser.results:
            prettyPrinter(row)
