# VERSION: 1.1
# AUTHORS: miIiano

import json
import re
import time
import urllib.request
import os
import logging
from base64 import urlsafe_b64decode
from novaprinter import prettyPrinter


# region: logging
FILE_PATH = os.path.dirname(os.path.realpath(__file__))
TOKEN_PATH = os.path.join(FILE_PATH, 'speedapp-token.json')
logging.basicConfig(
    filename=os.path.join(FILE_PATH, 'speedapp.log'),
    filemode='a',
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%d.%m %H:%M:%S',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
# endregion

class speedapp(object):
    ''' SpeedApp.IO  qBittorent Search Plugin '''

    # Change only below 3 lines
    username = "USERNAME_HERE"
    passwd  = "PASSWD_HERE"
    passkey = "PASSKEY_HERE"
    # DO NOT CHANGE
    request_body = {
        "username": username,
        "password": passwd
    }
    supported_categories = {
		'all':		  '',			
		'books':	  '6',
		'games':	  '11,52',
		'movies':	  '2,7,8,10,15,17,24,29,35,38,47,48,49,50,51,57,58,59,61,62,63,65',
		'music':	  '5,64',
		'software':	  '1,14,19,37',		
		'tv':         '41,43,44,45,46',
    	'anime':	  '3'
	}
    UA = " QbtPlugin-MiIiano https://github.com/miIiano/SpeedApp.io-qBittorent-search-plugin "
    token = ""
    url = 'https://speedapp.io'
    name = 'SpeedAppIO'

    def search(self, what: str, cat: str = "all") -> None:
        logger.debug("SEARCHING ->> %s in cat %s", what, cat)
        if self.login() != "OK": return None 
        category = self.supported_categories.get(cat, '')
        pattern = r'^(?:.*\/)?(tt\d{7})\/?$'
        match = re.match(pattern, what)
        imdb_check = match.group(1) if match else None
        query_type = "title" if imdb_check is None else "imdb"
        search_query = imdb_check or what
        if "imdb" == query_type :
            uri = f"https://speedapp.io/api/torrent?imdbId={search_query}&page=1&itemsPerPage=999999&direction=desc&sort=torrent.createdAt"
        if "title" == query_type :
            uri = f"https://speedapp.io/api/torrent?search={search_query}&page=1&itemsPerPage=999999&direction=desc&sort=torrent.createdAt"
        if category != '':
            for categ in category.split(','):
                uri+= f"&categories%5B%5D={categ}"
        try:
            headers = {
                    "Content-Type": "application/json",
                    "User-Agent": f'{self.UA}',
                    "Authorization":  f'Bearer {self.token}'
                }
            req = urllib.request.Request(uri, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = response.read().decode('utf-8')
            data = json.loads(data)
            for item in data:
                result = {
                    'desc_link': item['url'],
                    'name': item['name'],
                    'size': f"{item['size']} B",
                    'seeds': item['seeders'],
                    'leech': item['leechers'],
                    'engine_url': self.url,
                    'link': f"https://speedapp.io/rss/download/{item['id']}/{item['name']}.torrent?passkey={self.passkey}"
                }
                if 'is_freeleech' in item and item['is_freeleech'] == True:
                    result['name'] += ' 🆓 [Freeleech] '
                if 'is_double_upload' in item and item['is_double_upload'] == True:
                    result['name'] += ' 2️⃣🔼 [Double_UP] '
                if 'is_half_download' in item and item['is_half_download'] == True:
                    result['name'] += '  [Half_DW] '
                if 'imdb_id' in item and item['imdb_id'] != '':
                    result['name'] += ' [IMDB:  '+ item['imdb_id'] + '] '
                prettyPrinter(result)
        except Exception as oo_oo:
            logger.error("An error occurred: %s", str(oo_oo))

    def login(self):
        status = "KO"
        has_valid_creds = self.check_creds()
        try:
            if self.token != '' or has_valid_creds: return "OK"
            else:
                rq = json.dumps(self.request_body).encode('utf-8')
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
                }
                req = urllib.request.Request(self.url+"/api/login", data=rq, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.code == 201:
                        response_data = response.read().decode('utf-8')
                        data = json.loads(response_data)
                        self.token = data['token']
                        logger.debug(data)
                        with open(TOKEN_PATH, 'w', encoding='utf-8') as json_file:
                            json.dump(data, json_file)
                            json_file.write()
                            json_file.close()
                        logger.debug("Data written to %s",TOKEN_PATH )
                        status = "OK"
                    status = "KO"
            return status
        except urllib.error.URLError as o_o:
            logger.exception(o_o)
            logger.error("Error occurred: %s", str(o_o))
        except Exception as oo_oo:
            logger.error("An error occurred: %s", str(oo_oo))

    def check_creds(self):
        try:
            logger.debug("Trying to read from %s", TOKEN_PATH)
            current_directory = os.getcwd()
            logger.debug("Loading JSON file from: %s", {TOKEN_PATH})
            file_path = os.path.join(current_directory, TOKEN_PATH)
            with open(file_path, 'r', encoding='utf-8') as json_file:
                json_data = json.load(json_file)
                payload_b64 = json_data['token'].split('.')[1]
                padding = 4 - (len(payload_b64) % 4)
                payload_b64 += '=' * padding
                payload = json.loads(urlsafe_b64decode(payload_b64).decode('utf-8'))
                exp = payload['exp']
                timestamp = time.time()
                if exp > timestamp:
                    self.token = json_data['token']
                    return True
        except Exception as _e:
            logger.error("An error occurred: %s", str(_e))
            return False
