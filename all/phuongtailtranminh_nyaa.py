#VERSION: 1.04
#AUTHORS: Phuong Tran (phuongtm6994@gmail.com)
# LICENSING INFORMATION
from novaprinter import prettyPrinter
from helpers import retrieve_url, download_file
from html.parser import HTMLParser
import re
import math

# some other imports if necessary
class nyaa(object):
  url = 'https://sukebei.nyaa.si'
  name = 'Sukebei Nyaa' # spaces and special characters are allowed here
  # Which search categories are supported by this search engine and their corresponding id
  # Possible categories are ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
  supported_categories = {'all': '0', 'movies': '6', 'tv': '4', 'music': '1', 'games': '2', 'anime': '7', 'software': '3'}

  class NyaaParser(HTMLParser):
    def __init__(self, url):
      super().__init__()
      self.url = url
      self.rows = []
      self.in_tr = False
      self.in_td = False
      self.td_count = 0
      self.cell_text = []
      self.name_link_href = None
      self.name_title = None
      self.magnet = None
      self.size = '0'
      self.seeds = '-1'
      self.leech = '-1'

    def handle_starttag(self, tag, attrs):
      params = dict(attrs)
      if tag == 'tr':
        self.in_tr = True
        self.td_count = 0
        self.name_link_href = None
        self.name_title = None
        self.magnet = None
        self.size = '0'
        self.seeds = '-1'
        self.leech = '-1'
      elif self.in_tr and tag == 'td':
        self.td_count += 1
        self.in_td = True
        self.cell_text = []
      elif self.in_tr and tag == 'a':
        href = params.get('href', '')
        if self.td_count == 2 and self.name_link_href is None and href.startswith('/view/'):
          self.name_link_href = href
          self.name_title = params.get('title', '')
        elif href.startswith('magnet:'):
          self.magnet = href

    def handle_endtag(self, tag):
      if tag == 'tr':
        if self.in_tr and self.magnet and self.name_link_href:
          size = self.size
          unit = size[-3:]
          sizeInBytes = 0
          try:
            if unit == "GiB":
              sizeInBytes = float(size[:-3]) * 1073741824
            elif unit == "MiB":
              sizeInBytes = float(size[:-3]) * 1048576
            elif unit == "TiB":
              sizeInBytes = float(size[:-3]) * 1099511627776
            else:
              sizeInBytes = 0
          except (ValueError, IndexError):
            sizeInBytes = 0
          self.rows.append(dict(
            link=self.magnet,
            name=self.name_title or '',
            size=str(sizeInBytes),
            seeds=self.seeds,
            leech=self.leech,
            engine_url=self.url,
            desc_link=self.url + self.name_link_href
          ))
        self.in_tr = False
      elif tag == 'td':
        if self.in_td:
          text = ' '.join(''.join(self.cell_text).split())
          if self.td_count == 3:
            self.size = text
          elif self.td_count == 5:
            self.seeds = text
          elif self.td_count == 6:
            self.leech = text
        self.in_td = False

    def handle_data(self, data):
      if self.in_td:
        self.cell_text.append(data)

  def __init__(self):
    pass

  # DO NOT CHANGE the name and parameters of this function
  # This function will be the one called by nova2.py
  def search(self, what, cat='all'):
    # what is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
    # cat is the name of a search category in ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
    # q - query, f - filter, c - category
    base_url = 'https://sukebei.nyaa.si/?q=%s&f=0&c=0_0' % what
    response = retrieve_url(base_url)
    pagination_info = re.search(
      r'Displaying results \d+-(\d+) out of (\d+) results', response)
    if not pagination_info:
      return
    item_per_pages = int(pagination_info.group(1))
    total_page = int(pagination_info.group(2))
    if item_per_pages <= 0 or total_page <= 0:
      return
    number_of_page = math.ceil(float(total_page) / float(item_per_pages))
    for i in range(0, int(number_of_page)):
      base_url_with_query_and_page = base_url + '&p=%s' % str(i + 1)
      response = retrieve_url(base_url_with_query_and_page)
      parser = self.NyaaParser(self.url)
      parser.feed(response)
      parser.close()
      for res in parser.rows:
        prettyPrinter(res)
