# VERSION: 1.0
# AUTHORS: tolotp

import urllib.parse
import json
import datetime
from urllib import request
from novaprinter import prettyPrinter

class nekobt(object):
    url = "https://nekobt.to/"
    name = "NekoBT"
    
    supported_categories = {
        "all": ""
    }

    def format_size(self, size_bytes):
        try:
            size_bytes = float(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except Exception:
            return "0 MB"

    def search(self, what: str, cat="all"):
        what = urllib.parse.unquote(what)
        query = urllib.parse.quote_plus(what)
        
        search_url = f"{self.url}api/v1/torrents/search?query={query}"

        try:
            req = request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) qBittorrent Search",
                "Accept": "application/json"
            })
            response = request.urlopen(req)
            data = json.loads(response.read().decode('utf-8', errors='ignore'))
            
            # Buscamos la lista de torrents
            torrents = []
            if isinstance(data, dict):
                res_data = data.get("data", [])
                if isinstance(res_data, list):
                    torrents = res_data
                elif isinstance(res_data, dict):
                    torrents = res_data.get("results", res_data.get("torrents", []))
            elif isinstance(data, list):
                torrents = data

            if not torrents:
                print("Error: No se encontraron resultados o la palabra buscada no existe.")
                return

            for item in torrents:
                torrent_id = item.get("id")
                
                # Extraemos el título (intentamos auto_title si title está vacío)
                name = item.get("title")
                if not name:
                    name = item.get("auto_title", "Desconocido")
                
                # filesize viene todo junto según el JSON
                size = item.get("filesize", 0) 
                
                # Seeders y Leechers vienen como texto en el JSON
                seeds = item.get("seeders", 0)
                leech = item.get("leechers", 0)
                
                pub_date = "-1"
                # uploaded_at viene como string en milisegundos (ej: "1765432000000")
                created_at = item.get("uploaded_at", item.get("created_at"))
                if created_at:
                    try:
                        # Convertimos a float, dividimos entre 1000 y lo pasamos a entero
                        pub_date = str(int(float(created_at) / 1000))
                    except Exception:
                        pass
                
                # Magnet viene directo en el JSON
                magnet = item.get("magnet", "")
                if magnet:
                    download_link = magnet
                else:
                    infohash = item.get("infohash")
                    if infohash:
                        download_link = f"magnet:?xt=urn:btih:{infohash}&dn={urllib.parse.quote(name)}"
                    else:
                        download_link = f"{self.url}api/v1/torrents/download/{torrent_id}"
                
                desc_link = f"{self.url}torrents/{torrent_id}"
                
                res = {
                    "engine_url": self.url,
                    "name": name,
                    "size": self.format_size(size),
                    "seeds": str(seeds),
                    "leech": str(leech),
                    "link": download_link,
                    "desc_link": desc_link,
                    "pub_date": pub_date
                }
                prettyPrinter(res)
                
        except Exception as e:
            print(f"Error procesando la búsqueda: {e}")