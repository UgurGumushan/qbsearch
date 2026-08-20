# VERSION: 1.0
# AUTHORS: tolotp

import urllib.request
import urllib.parse
import json
import ssl
import datetime
from novaprinter import prettyPrinter 

class goggames(object):
    url = 'https://gog-games.to'
    
    name = 'GOG-Games' 
    supported_categories = {'all': '0'} 

    def search(self, what, cat='all'):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        query_text = urllib.parse.unquote(what).strip().lower()

        # cosas estetica
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

        items = data if isinstance(data, list) else data.get('data', [])
        
        if not items:
            prettyPrinter({
                'link': self.url,
                'name': "NO SE ENCONTRARON RESULTADOS",
                'size': '0', 'seeds': '0', 'leech': '0',
                'engine_url': self.url, 'desc_link': self.url
            })
            return

        for item in items:
            try:
                title_original = str(item.get('title', 'Juego Desconocido'))
                title_limpio = title_original.encode('ascii', 'ignore').decode('ascii')
                title_limpio = title_limpio.replace('|', '-')
                
                # ==========================================
                # TÍTULOS ESTÉTICOS CON EL SÍMBOLO
                if modo == "NOVEDADES":
                    # Formato: [.] Juego
                    title_final = f"[{query_text}] {title_limpio}"
                else:
                    title_final = title_limpio
                    
                # ==========================================
                # LÓGICA DE FECHAS (Ignorando los null)
                pub_date_str = '-1' 
                try:
                    if item.get('torrent_date'):
                        clean_date = str(item['torrent_date']).split('.')[0].replace('T', ' ')
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date_str = str(int(dt.timestamp()))
                    elif item.get('last_update') and str(item.get('last_update')).lower() != 'null':
                        clean_date = str(item['last_update']).split('.')[0].replace('T', ' ')
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date_str = str(int(dt.timestamp()))
                except Exception:
                    pass
                
                # ==========================================
                # REVISIÓN DEL INFOHASH (Mensaje "No torrent")
                infohash = item.get('infohash')
                
                if not infohash:
                    # Si no hay torrent, le agregamos el aviso y le pasamos la URL de la página web
                    title_final = f"{title_final} - No torrent"
                    enlace_descarga = self.url
                else:
                    # Si hay torrent, creamos el Magnet Link normal
                    encoded_name = urllib.parse.quote(title_final)
                    enlace_descarga = f"magnet:?xt=urn:btih:{infohash}&dn={encoded_name}"
                    
                res = {
                    'name': title_final,
                    'size': '-1', 
                    'seeds': '-1',
                    'leech': '-1',
                    'engine_url': self.url,
                    'desc_link': f"{self.url}/game/{item.get('slug', '')}",
                    'pub_date': pub_date_str,
                    'link': enlace_descarga
                }
                
                prettyPrinter(res)
                
            except Exception:
                continue
