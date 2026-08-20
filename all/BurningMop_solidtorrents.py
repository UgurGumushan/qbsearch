# VERSION: 2.0
# AUTHORS: BurningMop (burning.mop@yandex.com)

# LICENSING INFORMATION
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
from urllib.parse import urljoin

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter


class solidtorrents(object):
    url = 'https://bitsearch.eu'
    name = 'Bitsearch'
    supported_categories = {
        'all': ''
    }

    results_regex = r'bg-white rounded-lg shadow-sm border border-gray-200 p-6'

    def download_torrent(self, info):
        print(download_file(info))

    def parse_page(self, html):
        blocks = html.split(self.results_regex)[1:]
        count = 0
        for block in blocks:
            name_m = re.search(
                r'<h3[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S
            )
            magnet_m = re.search(r'href="(magnet:[^"]+)"', block)
            if not (name_m and magnet_m):
                continue
            size_m = re.search(
                r'<i class="fas fa-download"></i>\s*<span>([^<]+)</span>', block
            )
            seeds_m = re.search(
                r'text-green-600">\s*<i class="fas fa-arrow-up"></i>\s*'
                r'<span class="font-medium">([^<]+)</span>', block
            )
            leech_m = re.search(
                r'text-red-600">\s*<i class="fas fa-arrow-down"></i>\s*'
                r'<span class="font-medium">([^<]+)</span>', block
            )
            data = {
                'link': magnet_m.group(1),
                'name': re.sub(r'\s+', ' ', name_m.group(2)).strip(),
                'size': size_m.group(1) if size_m else '-1',
                'seeds': seeds_m.group(1) if seeds_m else '-1',
                'leech': leech_m.group(1) if leech_m else '-1',
                'engine_url': self.url,
                'desc_link': urljoin(self.url, name_m.group(1)),
            }
            prettyPrinter(data)
            count += 1
        return count

    def search(self, what, cat='all'):
        what = what.replace('%20', '+')
        what = what.replace(' ', '+')
        page = 1
        while page <= 3:
            page_url = f'{self.url}/search?q={what}&page={page}'
            retrieved_html = retrieve_url(page_url)
            count = self.parse_page(retrieved_html)
            if count == 0:
                break
            page += 1
