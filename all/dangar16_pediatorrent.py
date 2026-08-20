#VERSION: 1.00
# AUTHORS: Daniel Naranjo (garcianaranjodaniel@gmail.com)
# LICENSING INFORMATION

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter
# some other imports if necessary
import re

class pediatorrent(object):
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their corresponding id,
    possible categories are ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv').
    """

    url = 'https://pediatorrent.com/'
    name = 'PediaTorrent'
    supported_categories = {
        'all': '',
    }

    def __init__(self):
        """
        Some initialization
        """

    def download_torrent(self, url):
        """
        Providing this function is optional.
        It can however be interesting to provide your own torrent download
        implementation in case the search engine in question does not allow
        traditional downloads (for example, cookie-based download).
        """
        print(download_file(url))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        """
        Here you can do what you want to get the result from the search engine website.
        Everytime you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `what` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `cat` is the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """

        search_url = f"{self.url}buscar?q={what.replace('+','%20')}"
        html = retrieve_url(search_url)

        quantity = re.findall(r'<p.*?class="text-2xl text-lime-500 text-center.*?</p>', html)
        coincidencias = re.findall(r'\d+', quantity[0])
        
        quantity = int(coincidencias[2])
        pages = quantity // 17 + 1
        
        links = []

        for i in range(1, pages + 1):
            url = f"{self.url}buscar/page/{i}?q={what.replace('+','%20')}"
            html = retrieve_url(url)
            a_list = re.findall(r'<a.*?>', html)
            for a in a_list:
                url = re.findall(r'href=[\'"]?([^\'" >]+)', a)
                if len(url) > 0:
                    links.append(url[0])

        for i in links:
            if i.split("/")[-1].replace("-", " ") not in ["dmca", "ayuda", "documentales", "peliculas", f"buscar?q={what}", f"1?q={what.replace('+','%20')}"]:
                try: 
                    html = retrieve_url(i)
                    item = {}
                    item['seeds'] = '-1'
                    item['leech'] = '-1'
                    item['engine_url'] = self.url
                    item['desc_link'] = i
                    item['name'] = name = " ".join(i.split("/")[-1].split("-")[1:])
                    tipo = i.split("/")[3]
                    if tipo != "series":
                        a = re.findall(r'<a.*?>', html)
                        a = a[11:12]
                        url = re.findall(r'href=[\'"]?([^\'" >]+)', a[0])[0]
                        item['link'] = self.url + url[1:]
                        item['size'] = -1
                        prettyPrinter(item)
                    else:
                        tds = re.findall(r'<td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium ml-auto">(.*?)</td>', html, re.M|re.I|re.S)
                        for td in tds:
                            td_link = re.findall(r'href=[\'"]?([^\'" >]+)', td, re.DOTALL)
                            a = td_link[0]

                            try:
                                download_link = a
                                item['link'] = self.url + download_link[1:]
                                item['size'] = -1
                                item['name'] = name + td_link[0]
                                prettyPrinter(item)
                            except Exception:
                                continue
                except Exception:
                    continue
