#VERSION: 1.0
# AUTHORS: caiocinel, Bioux1

import json
from urllib.parse import unquote
from helpers import retrieve_url
from novaprinter import prettyPrinter


class onlinefix(object):
    url = 'https://online-fix.me/'
    name = 'Online-Fix'
    supported_categories = {'all': ''}

    def search(self, what, cat='all'):
        search_url = 'https://hydralinks.cloud/sources/onlinefix.json'

        response = retrieve_url(search_url)
        response_json = json.loads(response)

        what = unquote(what)
        search_terms = what.lower().split()

        for result in response_json['downloads']:
            if any(term in result['title'].lower() for term in search_terms):
                res = {'link': self.download_link(result),
                       'name': result['title'],
                       'size': result['fileSize'],
                       'seeds': '-1',
                       'leech': '-1',
                       'engine_url': self.url,
                       'desc_link': '-1'}
                prettyPrinter(res)

    def download_link(self, result):
            return result['uris'][0]
