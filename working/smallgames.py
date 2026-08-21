# VERSION: 1.03

from __future__ import annotations

import os
import re
import ssl
import tempfile
from typing import ClassVar
from urllib.request import urlopen

# qBt
from novaprinter import prettyPrinter


# noinspection PyPep8Naming
class smallgames:
    url = "http://small-games.info/"
    name = 'small-games.info'
    result: ClassVar[dict[str, object | str]]  = {
        'seeds': -1,
        'leech': -1,
        'engine_url': url
    }
    supported_categories: ClassVar[dict[str, bool]] = {'all': True,
                            'games': True}

    def download_torrent(self, url):
        file, path = tempfile.mkstemp('.torrent')
        file = os.fdopen(file, "wb")

        dat = self.get_url(url)
        data = dat.decode('utf-8', 'replace')
        if data == 'No link found!' or data == 'some error':
            return
        else:
            # Write it to a file
            file.write(dat)
            file.close()
            # return file path
            print(path + " " + url)

    def search(self, what, cat='all'):
        query = "https://small-games.info/?go=search&go=search&search_text=" + what
        data = self.get_url(query).decode('utf-8', 'replace')
        match = re.compile('<a title=\"(.*?)\"\\shref=\"/.*?i=(\\d*).*?Скачать\\sигру\\s\\((.{2,11})\\)')
        results = match.findall(data)
        name_clean = re.compile('[A-Za-z0-9].*')

        for res in results:
            self.result['name'] = name_clean.findall(res[0])[0]
            self.result['link'] = self.url + "getTorrent.php?direct=1&gid=" + res[1]
            self.result['desc_link'] = self.url + "?go=game&c=61&i=" + res[1]
            #  it always MB, and the M from the string is a weird russian one
            #  so pretty printer will not recognize it
            self.result['size'] = res[2][:-3] + 'MB'
            prettyPrinter(self.result)

    @staticmethod
    def get_url(url):
        context = ssl._create_unverified_context()
        return urlopen(url, context=context).read()


if __name__ == "__main__":
    engine = smallgames()
    engine.search('eco')