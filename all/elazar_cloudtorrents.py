# VERSION: 1.0
# AUTHORS: Matthew Turland (me@matthewturland.com)

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

from datetime import datetime
from helpers import retrieve_url
import json
from novaprinter import prettyPrinter
from urllib.parse import urlencode


class cloudtorrents(object):
    url = "https://cloudtorrents.com"
    name = "CloudTorrents"
    supported_categories = {
        "all": None,
        "anime": "1",
        "software": "2",
        "books": "3",
        "games": "4",
        "movies": "5",
        "music": "6",
        "tv": "8",
    }

    def quote_via(self, string, safe="/", encoding=None, errors=None):
        return str(string, "utf-8") if isinstance(string, bytes) else string

    def search(self, what, cat="all"):
        query = {
            "offset": 0,
            "limit": 50,
            "query": what,
        }
        if cat != "all" and cat in self.supported_categories:
            query["torrent_type"] = self.supported_categories[cat]
        items = []
        while True:
            url = "https://api.cloudtorrents.com/search/?" \
                + urlencode(query, quote_via=self.quote_via)
            encoded = retrieve_url(url)
            decoded = json.loads(encoded)
            for result in decoded["results"]:
                torrent = result["torrent"]
                desc_link = self.url \
                    + "/" + torrent["torrentType"]["name"].lower() \
                    + "/" + str(result["id"])
                pub_date = int(datetime.fromisoformat(torrent["uploadedAt"]).timestamp())
                item = {
                    "link": torrent["torrentMagnet"],
                    "name": torrent["name"],
                    "size": torrent["size"],
                    "seeds": torrent["seeders"],
                    "leech": torrent["leechers"],
                    "engine_url": self.url,
                    "desc_link": desc_link,
                    "pub_date": pub_date,
                }
                items.append(item)
            if decoded["next"] is None:
                break
            query["offset"] += query["limit"]
        items.sort(reverse=True, key=lambda item: item["seeds"])
        for item in items:
            prettyPrinter(item)
