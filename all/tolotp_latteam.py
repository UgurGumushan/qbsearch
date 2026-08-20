# VERSION: 1.0
# AUTHORS: tolotp

import os
import configparser
import urllib.parse
import json
import datetime
from tempfile import mkstemp
from urllib import request
from novaprinter import prettyPrinter

# ====================================================================
# SISTEMA DE CONFIGURACIÓN AUTOMÁTICO (.ini)
# ====================================================================
USER_HOME = os.path.expanduser("~")
CONFIG_FILE = os.path.join(USER_HOME, "latteam_config.ini")

def get_api_key():
    config = configparser.ConfigParser(interpolation=None)
    
    if not os.path.exists(CONFIG_FILE):
        config['login'] = {
            'api_key': ''
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return ""
    
    config.read(CONFIG_FILE, encoding='utf-8')
    try:
        if config.has_option('login', 'api_key'):
            return config.get('login', 'api_key').strip()
        elif config.has_option('login', 'cookie'):
            return config.get('login', 'cookie').strip()
        return ""
    except Exception:
        return ""

API_KEY = get_api_key()

class latteam(object):
    url = "https://lat-team.com/"
    name = "Lat-Team"
    
    supported_categories = {
        "all": "",
        "movies": "1",
        "tv": "2",
        "music": "3",
        "games": "4",
        "anime": "5",
        "books": "18"
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
        if not API_KEY:
            print(f"Por favor, configura tu API Key en el archivo: {CONFIG_FILE}")
            return

        what = urllib.parse.unquote(what)
        query = urllib.parse.quote(what)
        categ = self.supported_categories.get(cat, "")
        
        search_url = f"{self.url}api/torrents/filter?name={query}&api_token={API_KEY}"
        if categ:
            search_url += f"&categories[]={categ}"

        try:
            req = request.Request(search_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json"
            })
            response = request.urlopen(req)
            data = json.loads(response.read().decode('utf-8', errors='ignore'))
            
            torrents = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(torrents, list):
                torrents = []

            for item in torrents:
                attrs = item.get("attributes", item)
                
                torrent_id = item.get("id")
                name = attrs.get("name", "Desconocido")
                size = attrs.get("size", 0)
                seeds = attrs.get("seeders", 0)
                leech = attrs.get("leechers", 0)
                
                pub_date = "-1"
                created_at = attrs.get("created_at")
                if created_at:
                    try:
                        clean_date = created_at.split('.')[0].replace('T', ' ')
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date = str(int(dt.timestamp()))
                    except Exception:
                        pub_date = str(created_at)
                
                # CORRECCIÓN: Ruta exacta basada en la web (sin /api/)
                # Si la API entrega un "download_link" oficial lo usamos, si no, armamos la ruta correcta.
                download_link = attrs.get("download_link", f"{self.url}torrents/download/{torrent_id}")
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
            print(f"Error en la API de Lat-Team: {e}")

    def download_torrent(self, url):
        if not API_KEY:
            return

        # Anexamos la API Key a la URL de descarga para saltarnos el 2FA
        download_url = f"{url}?api_token={API_KEY}" if "?" not in url else f"{url}&api_token={API_KEY}"

        fd, path = mkstemp(".torrent")
        os.close(fd)
        
        try:
            req = request.Request(download_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Authorization": f"Bearer {API_KEY}",
                "Accept": "application/x-bittorrent, application/octet-stream, */*"
            })
            with request.urlopen(req) as response:
                with open(path, "wb") as file:
                    file.write(response.read())
            
            # Si el archivo se guarda con éxito, se lo pasamos a qBittorrent para que abra la ventana
            print(f"{path} {url}")
            
        except Exception as e:
            print(f"Error descargando torrent: {e}")