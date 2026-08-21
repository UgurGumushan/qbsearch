# VERSION: 1.0
"""
NekoBT anime torrent search. Queries the site's JSON API; each torrent's link
is its magnet when present, else built from the infohash, falling back to the
torrent download endpoint.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import ClassVar, TypedDict, cast
from urllib import request

from novaprinter import SearchResults, prettyPrinter


class TorrentItem(TypedDict, total=False):
    id: int
    title: str
    auto_title: str
    filesize: int | float | str
    seeders: int
    leechers: int
    uploaded_at: int | float | str
    created_at: int | float | str
    magnet: str
    infohash: str


class ApiData(TypedDict, total=False):
    results: list[TorrentItem]
    torrents: list[TorrentItem]


class ApiResponse(TypedDict, total=False):
    data: ApiData | list[TorrentItem]


class nekobt:
    url = "https://nekobt.to/"
    name = "NekoBT"

    supported_categories: ClassVar[dict[str, str]] = {"all": ""}

    def format_size(self, size_bytes: float | str) -> str:
        try:
            size_bytes = float(size_bytes)
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except Exception:
            return "0 MB"

    def search(self, what: str, cat: str = "all"):
        what = urllib.parse.unquote(what)
        query = urllib.parse.quote_plus(what)

        search_url = f"{self.url}api/v1/torrents/search?query={query}"

        try:
            req = request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) qBittorrent Search",
                    "Accept": "application/json",
                },
            )
            response = request.urlopen(req)
            data: ApiResponse | list[TorrentItem] = json.loads(
                response.read().decode("utf-8", errors="ignore")
            )

            # The API wraps the list in "data", sometimes under "results"
            # or "torrents"; it may also answer with a bare list.
            torrents: list[TorrentItem] = []
            if isinstance(data, dict):
                res_data: object = data.get("data", [])
                if isinstance(res_data, list):
                    torrents = cast(list[TorrentItem], res_data)
                elif isinstance(res_data, dict):
                    nested: object = res_data.get("results")
                    if not isinstance(nested, list):
                        nested = res_data.get("torrents")
                    if isinstance(nested, list):
                        torrents = cast(list[TorrentItem], nested)
            else:
                torrents = data

            if not torrents:
                print("Error: No se encontraron resultados o la palabra buscada no existe.")
                return

            for item in torrents:
                torrent_id = item.get("id")

                # Use the title; fall back to auto_title when it is empty
                name_value = item.get("title")
                if isinstance(name_value, str) and name_value:
                    name = name_value
                else:
                    auto_title = item.get("auto_title")
                    name = auto_title if isinstance(auto_title, str) and auto_title else "Desconocido"

                size_value = item.get("filesize")
                if isinstance(size_value, (int, float)):
                    size: float | str = float(size_value)
                elif isinstance(size_value, str):
                    size = size_value
                else:
                    size = 0.0

                seeds = item.get("seeders", 0)
                leech = item.get("leechers", 0)

                pub_date: int = -1
                # uploaded_at / created_at arrive as millisecond-epoch strings
                created_at: int | float | str | None = item.get("uploaded_at")
                if created_at is None:
                    created_at = item.get("created_at")
                if created_at:
                    try:
                        # Convert to a second-epoch timestamp
                        pub_date = int(float(created_at) / 1000)
                    except Exception:
                        pass

                # Magnet is provided directly by the API when available
                magnet = item.get("magnet", "")
                if magnet:
                    download_link = magnet
                else:
                    infohash = item.get("infohash")
                    if infohash:
                        download_link = (
                            f"magnet:?xt=urn:btih:{infohash}&dn={urllib.parse.quote(name)}"
                        )
                    else:
                        download_link = f"{self.url}api/v1/torrents/download/{torrent_id}"

                desc_link = f"{self.url}torrents/{torrent_id}"

                res: SearchResults = {
                    "engine_url": self.url,
                    "name": name,
                    "size": self.format_size(size),
                    "seeds": int(seeds),
                    "leech": int(leech),
                    "link": download_link,
                    "desc_link": desc_link,
                    "pub_date": pub_date,
                }
                prettyPrinter(res)

        except Exception as e:
            print(f"Error procesando la búsqueda: {e}")
