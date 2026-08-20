# VERSION: 2.0
# AUTHORS: Koba (autor original) / tolotp (modifique y retoque el plugin)
# MODIFIED: Fix + calcular fecha de subida + crear unionfansub_config.ini en carpeta de usuario C:\Users\[tu nombre de perfil de windows] o en linux /home/tunombre/

import os
import urllib.parse
import re
import time
import configparser
from datetime import datetime
from tempfile import mkstemp
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib import request
from urllib.error import URLError
from urllib.parse import urlencode

from novaprinter import prettyPrinter

# ====================================================================
# SISTEMA DE CONFIGURACIÓN AUTOMÁTICO (.ini)
# ====================================================================
# Detecta la "Carpeta Personal" del usuario en Windows C:\Users\TuNombreDeUsuario o Linux /home/tunombre/
USER_HOME = os.path.expanduser("~")
CONFIG_FILE = os.path.join(USER_HOME, "unionfansub_config.ini")

def get_credentials():
    config = configparser.ConfigParser()
    
    # Si el archivo NO existe, lo creamos con los campos vacíos en la ruta fácil
    if not os.path.exists(CONFIG_FILE):
        config['login'] = {
            'usuario': '',
            'contraseña': ''
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return "", ""
    
    # Si el archivo SÍ existe, lo leemos
    config.read(CONFIG_FILE, encoding='utf-8')
    try:
        u = config.get('login', 'usuario').strip()
        p = config.get('login', 'contraseña').strip()
        return u, p
    except (configparser.NoSectionError, configparser.NoOptionError):
        return "", ""

# Obtenemos las credenciales
USER, PASS = get_credentials()

class Parser(HTMLParser):
    def __init__(self, url: str):
        super().__init__()

        self.url = url
        self.current_res = {}
        self.current_item = None
        self.in_table = False

    def handle_starttag(self, tag: str, attrs: list):
        attr = dict(attrs)

        self.in_table = self.in_table or tag == "table"
        if not self.in_table:
            return

        if tag == "span":
            self.current_item = None

        if attr.get("class") == "name" and tag == "b":
            self.current_item = "name"

        if tag == "a" and "href" in attr:
            link = attr.get("href")

            if link is not None:
                if link.startswith("peerlist.php"):
                    if link.endswith("leechers"):
                        self.current_item = "leech"
                    else:
                        self.current_res["leech"] = 0

                if link.startswith("details.php") and link.endswith("hit=1"):
                    dl = link[:-6].replace("details.php?id=", "download.php?torrent=")
                    self.current_res["link"] = self.url + dl + "&aviso=1"
                    self.current_res["desc_link"] = self.url + link[:-6]
                    self.current_res["engine_url"] = self.url

        if tag == "font":
            if attr.get("color", "#000000"):
                self.current_item = "seeds"
            else:
                self.current_res["seeds"] = 0

    def handle_data(self, data):
        if not self.in_table:
            return

        clean_data = data.strip()

        if self.current_item == "name":
            self.current_res[self.current_item] = data
            
        if data.endswith("GB") or data.endswith("MB"):
            self.current_res["size"] = data.strip().replace(",", ".")
            
        if self.current_item == "seeds" and data != "\n":
            self.current_res[self.current_item] = data
            
        if self.current_item == "leech" and data != "\n":
            self.current_res[self.current_item] = data

        if self.current_item != "name" and clean_data:
            if re.match(r'^(\d+[wdhmy])+$', clean_data):
                total_seconds = 0
                matches = re.findall(r'(\d+)([wdhmy])', clean_data)
                
                for val, unit in matches:
                    val = int(val)
                    if unit == 'w': total_seconds += val * 604800
                    elif unit == 'd': total_seconds += val * 86400
                    elif unit == 'h': total_seconds += val * 3600
                    elif unit == 'm': total_seconds += val * 60
                    elif unit == 'y': total_seconds += val * 31536000
                
                calculated_time = time.time() - total_seconds - 86400
                dt = datetime.fromtimestamp(calculated_time)
                dt_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                self.current_res["pub_date"] = str(int(dt_midnight.timestamp()))

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        if not self.in_table:
            return

        if tag == "font":
            self.current_item = None

        if self.current_res and tag == "tr":
            prettyPrinter(self.current_res)
            self.current_res = {}
            self.current_item = None


class unionfansub:
    url = "https://torrent.unionfansub.com/"
    name = "Union Fansub"
    supported_categories = {
        "all": "0",
        "tv": "9",
        "anime": "1",
        "movies": "15",
        "music": "16",
        "games": "18",
        "software": "11",
    }

    def __init__(self):
        self.session = None
        # Solo intenta hacer login si el usuario llenó el .ini
        if USER and PASS:
            self._login(USER, PASS)

    def _login(self, username: str, password: str):
        login_url = "https://foro.unionfansub.com/member.php?action=login"

        params = urlencode(
            {
                "username": username,
                "password": password,
                "submit": "Iniciar+sesión",
                "action": "do_login",
            }
        ).encode("utf-8")

        header = {
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        cookie_jar = CookieJar()
        session = request.build_opener(request.HTTPCookieProcessor(cookie_jar))

        try:
            req = request.Request(login_url, data=params, headers=header)
            session.open(req)
            self.session = session
        except URLError as e:
            print(f"Error al conectarse: {e.reason}")

    def search(self, what: str, cat="all"):
        if not self.session:
            # Si no hay sesión, avisamos por consola. qBittorrent no mostrará resultados.
            print(f"Por favor, configura tus credenciales en: {CONFIG_FILE}")
            return

        categ = self.supported_categories.get(cat, "0")
        query = urllib.parse.quote(what)
        url_base = f"{self.url}browse.php?search={query}&c{categ}"

        parser = Parser(self.url)

        for page in range(3): 
            try:
                search_url = f"{url_base}&page={page}"
                req = request.Request(search_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                response = self.session.open(req)
                html = response.read().decode('utf-8', errors='ignore')
                
                if "Nada encontrado" in html or "member.php?action=login" in html:
                    break
                    
                parser.feed(html)
            except Exception as e:
                print(f"Error retrieving search results: {e}")
                break

        parser.close()

    def download_torrent(self, url):
        f, path = mkstemp(".torrent")

        try:
            if self.session:
                req = request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                with self.session.open(req) as response:
                    with open(f, "wb") as file:
                        file.write(response.read())
        except Exception as e:
            print(f"Error downloading torrent: {e}")

        print(f"{path} {url}")