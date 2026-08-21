# VERSION: 1.0
"""
GOG-Games game search. Queries the site's REST API and builds magnet links
from the infohash; entries without a torrent are listed with a "No torrent"
note and the site URL as their download link.
"""
import datetime
import json
import ssl
import urllib.parse
import urllib.request
from typing import ClassVar

from novaprinter import SearchResults, prettyPrinter


def _extract_items(data: object) -> list[dict[str, object]]:
    """Return only object entries from either supported API response shape."""
    raw_items: object = data
    if isinstance(data, dict):
        raw_items = data.get('data', [])
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


class goggames:
    url = 'https://gog-games.to'
    
    name = 'GOG-Games' 
    supported_categories: ClassVar[dict[str, str]]  = {'all': '0'} 

    def search(self, what: str, cat: str = 'all') -> None:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        query_text = urllib.parse.unquote(what).strip().lower()

        # Non-word queries just list the newest torrents
        if query_text in ['.', '*', '!']:
            endpoint = f"{self.url}/api/web/recent-torrents"
            modo = "NOVEDADES"
        else:
            query_encoded = urllib.parse.quote(query_text)
            endpoint = f"{self.url}/search?page=1&search={query_encoded}&sort_by=lastUpdateDescending"
            modo = "BÚSQUEDA"
        
        req = urllib.request.Request(endpoint, headers={
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
        
        try:
            response = urllib.request.urlopen(req, context=ctx)
            data = json.loads(response.read().decode('utf-8'))
        except Exception:
            return

        # The API answers a bare list, or a dict wrapping the list in "data"
        items = _extract_items(data)

        if not items:
            prettyPrinter(
                SearchResults(
                    link=self.url,
                    name="NO SE ENCONTRARON RESULTADOS",
                    size='0',
                    seeds=0,
                    leech=0,
                    engine_url=self.url,
                    desc_link=self.url,
                )
            )
            return

        for item in items:
            try:
                title_original = str(item.get('title', 'Juego Desconocido'))
                # Drop non-ASCII leftovers and the '|' separator used as a title delimiter
                title_limpio = title_original.encode('ascii', 'ignore').decode('ascii')
                title_limpio = title_limpio.replace('|', '-')

                # Newest-torrents queries get the query symbol prefixed, e.g. "[.] Game"
                if modo == "NOVEDADES":
                    title_final = f"[{query_text}] {title_limpio}"
                else:
                    title_final = title_limpio
                    
                # Publish date: prefer torrent_date, fall back to last_update;
                # skip nulls and keep '-1' so qBitt treats it as unknown
                pub_date_str = -1
                try:
                    if item.get('torrent_date'):
                        clean_date = str(item['torrent_date']).split('.')[0].replace('T', ' ')
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date_str = int(dt.timestamp())
                    elif item.get('last_update') and str(item.get('last_update')).lower() != 'null':
                        clean_date = str(item['last_update']).split('.')[0].replace('T', ' ')
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date_str = int(dt.timestamp())
                except Exception:
                    pass
                
                # With an infohash the link is a magnet; without one, flag the
                # entry as torrent-less and point at the site instead
                infohash = item.get('infohash')

                if not isinstance(infohash, str) or not infohash:
                    title_final = f"{title_final} - No torrent"
                    enlace_descarga = self.url
                else:
                    encoded_name = urllib.parse.quote(title_final)
                    enlace_descarga = f"magnet:?xt=urn:btih:{infohash}&dn={encoded_name}"
                    
                slug = item.get('slug', '')
                slug_text = slug if isinstance(slug, str) else str(slug)
                res: SearchResults = {
                    'name': title_final,
                    'size': '-1', 
                    'seeds': -1,
                    'leech': -1,
                    'engine_url': self.url,
                    'desc_link': f"{self.url}/game/{slug_text}",
                    'pub_date': pub_date_str,
                    'link': enlace_descarga
                }
                
                prettyPrinter(res)
                
            except Exception:
                continue
