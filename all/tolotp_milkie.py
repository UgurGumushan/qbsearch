# VERSION: 1.0
# AUTHORS: tolotp

import urllib.request
import urllib.parse
import json
import ssl
import os
import configparser
from novaprinter import prettyPrinter 

user_home_dir = os.path.expanduser('~')
config_file = os.path.join(user_home_dir, 'milkie.ini')

if not os.path.exists(config_file):
    config = configparser.ConfigParser()
    config['MILKIE'] = {'api_key': ''}
    with open(config_file, 'w') as configfile:
        config.write(configfile)

class milkie(object):
    url = 'https://milkie.cc'
    name = 'Milkie'
    
    # Mapeo de las categorías de qBittorrent a los IDs
    supported_categories = {
        'all': '',       
        'movies': '1',   
        'tv': '2',       
        'music': '3',    
        'games': '4',    
        'books': '5',    
        'software': '6'  
    } 

    def __init__(self):
        self.api_key = ''
        self.load_config()

    def load_config(self):
        config = configparser.ConfigParser()
        # Aquí ya solo leemos, porque el archivo ya se creó al instalar
        if os.path.exists(config_file):
            config.read(config_file)
            if 'MILKIE' in config and 'api_key' in config['MILKIE']:
                self.api_key = config['MILKIE']['api_key']

    def search(self, what, cat='all'):
        if not self.api_key or self.api_key == '':
            prettyPrinter({
                'link': self.url,
                'name': f"ERROR: Pon tu API Key en el archivo: {config_file}",
                'size': '0', 'seeds': '0', 'leech': '0',
                'engine_url': self.url, 'desc_link': self.url
            })
            return

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        search_endpoint = f"{self.url}/api/v1/torrents"
        params = {'ps': '100'} 
        
        if what != 'all':
            params['query'] = urllib.parse.unquote(what)
            
        if cat != 'all' and cat in self.supported_categories:
            params['categories'] = self.supported_categories[cat]
            
        query_string = urllib.parse.urlencode(params)
        full_url = f"{search_endpoint}?{query_string}"
        
        req = urllib.request.Request(full_url, headers={
            'x-milkie-auth': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
        
        try:
            response = urllib.request.urlopen(req, context=ctx)
            data = json.loads(response.read().decode('utf-8'))
            
            if 'torrents' not in data or not data['torrents']:
                return

            encoded_api_key = self.api_key.replace('+', '%2B')

            for torrent in data['torrents']:
                res = {
                    'link': f"{self.url}/api/v1/torrents/{torrent['id']}/torrent?key={encoded_api_key}",
                    'name': str(torrent.get('releaseName', 'Nombre Desconocido')),
                    'size': str(torrent.get('size', 0)),
                    'seeds': str(torrent.get('seeders', 0)),
                    'leech': str(torrent.get('leechers', 0)),
                    'engine_url': self.url,
                    'desc_link': f"{self.url}/browse/{torrent['id']}"
                }
                
                prettyPrinter(res)
                
        except Exception as e:
            res = {
                'link': self.url,
                'name': f"ERROR DETECTADO: {str(e)}",
                'size': '0', 'seeds': '0', 'leech': '0',
                'engine_url': self.url, 'desc_link': self.url
            }
            prettyPrinter(res)