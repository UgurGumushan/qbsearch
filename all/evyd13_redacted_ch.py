# VERSION: 1.00
# AUTHORS: evyd13 (Evelien Dekkers)

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

import urllib.request
import json
import os
import tempfile
import gzip
import io
from novaprinter import prettyPrinter


class redacted_ch(object):
    url = 'https://redacted.ch'
    name = 'redacted.ch'
    supported_categories = {
        'all': None,
        'music': 1,
        'software': 2,
    }

    def __init__(self):
        """
        Initialization.
        
        SET YOUR API TOKEN HERE
        
        """
        self.api_token = ' YOUR API TOKEN HERE (NEEDS TORRENT SCOPE) '
        self.api_url = 'https://redacted.ch/ajax.php'

    def download_torrent(self, info):
        self.download_file(info)

    def search(self, what, cat='all'):
        search_kwargs = {
            'action': 'browse',
            'searchstr': what,
            'order_by': 'time',
            'order_way': 'desc',
            'group_results': 1,
        }

        if self.supported_categories[cat] != None:
            search_kwargs.update({"filter_cat[{}]".format(self.supported_categories[cat]): 1})

        url = self.format_url(search_kwargs)
        result_json = self.retrieve_url(url)
        
        for album in result_json['response']['results']:
            for torrent in album['torrents']:
                torrent_dict = {
                    'link': self.format_url({
                        'action': 'download',
                        'id': torrent['torrentId']
                    }),
                    'name': "{} - {} ({}) [{} / {} {}]{}".format(
                        album['artist'],
                        album['groupName'],
                        album['groupYear'],
                        torrent['media'],
                        torrent['format'],
                        torrent['encoding'],

                        " ({})".format(
                            " / ".join([ str(x) for x in [torrent['remasterYear'], torrent['remasterCatalogueNumber'], torrent['remasterTitle']] if str(x) ])
                        ) if (torrent['remasterYear'] or torrent['remasterCatalogueNumber'] or torrent['remasterTitle']) else "",
                    ),
                    'size': "{} B".format(torrent['size']),
                    'seeds': torrent['seeders'],
                    'leech': torrent['leechers'],
                    'engine_url': self.url,
                    'desc_link': "{}/torrents.php?id={}&torrentid={}".format(self.url, album['groupId'], torrent['torrentId'])
                }
                prettyPrinter(torrent_dict)

        
    def format_url(self, dict_kwargs):
        return "{}?{}".format(
            self.api_url,
            "&".join(
                ["{}={}".format(k, v) for k, v in dict_kwargs.items()]
            )
        )

    def retrieve_url(self, url):
        req = urllib.request.Request(url, headers={'Authorization': self.api_token})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return ""
        dat = response.read()
        return json.loads(dat)
    
    def download_file(self, url, referer=None):
        file, path = tempfile.mkstemp()
        file = os.fdopen(file, "wb")
        # Download url
        req = urllib.request.Request(url, headers={'Authorization': self.api_token})
        if referer is not None:
            req.add_header('referer', referer)
        response = urllib.request.urlopen(req)
        dat = response.read()
        # Check if it is gzipped
        if dat[:2] == b'\x1f\x8b':
            # Data is gzip encoded, decode it
            compressedstream = io.BytesIO(dat)
            gzipper = gzip.GzipFile(fileobj=compressedstream)
            extracted_data = gzipper.read()
            dat = extracted_data

        # Write it to a file
        file.write(dat)
        file.close()
        # return file path
        print (path + " " + url)