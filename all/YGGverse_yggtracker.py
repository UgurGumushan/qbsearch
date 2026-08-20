# VERSION: 1.1.0
# LICENSE: MIT
# AUTHORS: https://github.com/YGGverse/qbittorrent-yggtracker-search-plugin

import json
from urllib.parse import urlencode, unquote

from novaprinter import prettyPrinter
from helpers import retrieve_url

class yggtracker(object):

  name = 'YGGtracker'
  url = 'https://github.com/YGGverse/YGGtracker'
  supported_categories = {
    'all':[],
    'anime':[],
    'books':[],
    'games':[],
    'movies':[],
    'music':[],
    'pictures':[],
    'software':[],
    'tv':[]
  }

  def __init__(self):
    pass

  def search(self, what, cat='all'):

    # get distributed nodes registry
    nodes = retrieve_url("https://raw.githubusercontent.com/YGGverse/qbittorrent-yggtracker-search-plugin/main/nodes.json")
    nodes_json = json.loads(nodes)

    # check empty response
    if len(nodes_json) == 0:
      return

    # parse results
    for node in nodes_json:

      # apply query request
      what = unquote(what)
      params = {
        'query': what,
        'filter': 'true'
      }

      # apply categories filter
      categories = []
      for category in node['categories'][cat]:
        categories.append(category)

      if len(categories) > 0:
        params['categories'] = '|'.join(categories)

      # send api request
      response = retrieve_url(node['url'] % urlencode(params))
      response_json = json.loads(response)

      # check empty response
      if len(response_json['torrents']) == 0:
        continue

      # parse results
      for item in response_json['torrents']:
        res = {
          'link': item['torrent']['file']['url'],
          'name': item['torrent']['file']['name'],
          'size': str(item['torrent']['file']['size']) + " B",
          'seeds': item['torrent']['scrape']['seeders'],
          'leech': item['torrent']['scrape']['leechers'],
          'engine_url': response_json['tracker']['url'],
          'desc_link': item['torrent']['url']
        }
        prettyPrinter(res)