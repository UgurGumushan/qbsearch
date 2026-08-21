# VERSION: 1.1

import json
from datetime import datetime
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

from helpers import retrieve_url
from novaprinter import prettyPrinter


class subsplease:
    url = 'https://subsplease.org/'
    name = 'SubsPlease'
    supported_categories: ClassVar[dict[str, str]]  = {'all': ''}

    def search(self, what, cat='all'):
        for page in range(6):
            search_url = f"https://subsplease.org/api/?f=search&tz=$&s={what}&p={page}"
            response = retrieve_url(search_url)
            response_json = json.loads(response)
            if not response_json:
                break

            for result_name, result_data in response_json.items():
                release_date = datetime.strptime(
                    result_data['release_date'], "%a, %d %b %Y %H:%M:%S %z"
                )
                for download in result_data["downloads"]:
                    magnet_link = download["magnet"]
                    parsed_url = urlparse(magnet_link)
                    size = parse_qs(parsed_url.query)['xl'][0]

                    res = {
                        'link': magnet_link,
                        'name': f"[SubsPlease] {result_name} ({download['res']}p)",
                        'size': size,
                        'seeds': '-1',
                        'leech': '-1',
                        'engine_url': search_url,
                        'desc_link': '-1',
                        'pub_date': int(release_date.timestamp()),
                    }
                    prettyPrinter(res)