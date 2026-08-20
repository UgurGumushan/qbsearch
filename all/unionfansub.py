# VERSION: 1.5
# AUTHORS: Koba (CrimsonKoba@protonmail.com)
from tempfile import mkstemp
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib import request
from urllib.error import URLError
from urllib.parse import urlencode

from helpers import retrieve_url
from novaprinter import prettyPrinter

USER = "USUARIO"
PASS = "CONTRASEÑA"


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

        if self.current_item == "name":
            self.current_res[self.current_item] = data
        if data.endswith("GB") or data.endswith("MB"):
            self.current_res["size"] = data.strip().replace(",", ".")
        if self.current_item == "seeds" and data != "\n":
            self.current_res[self.current_item] = data
        if self.current_item == "leech" and data != "\n":
            self.current_res[self.current_item] = data

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
        self._login(USER, PASS)

    def _login(self, username: str, password: str):
        login_url = "https://foro.unionfansub.com/member.php?action=login"

        params: bytes = urlencode(
            {
                "username": username,
                "password": password,
                "submit": "Iniciar+sesión",
                "action": "do_login",
            }
        ).encode("utf-8")

        header = {
            "Connection": "keep-alive",
            "User-Agent": "qBittorrent/4",
        }

        cookie_jar = CookieJar()
        session: request.OpenerDirector = request.build_opener(
            request.HTTPCookieProcessor(cookie_jar)
        )

        try:
            session.open(request.Request(login_url, params, header))
            self.session: request.OpenerDirector = session
        except URLError as e:
            print(f"Error al conectarse: {e.reason}")

    def search(self, what: str, cat = "all"):
        categ = self.supported_categories.get(cat)
        url: str = f"{self.url}browse.php?search={what}&c{categ}"

        page = 0
        results = []
        parser = Parser(self.url)

        while page <= 10:
            try:
                html = retrieve_url(f"{url}&page={str(page)}")
                parser.feed(html)
            except Exception as e:
                print(f"Error retrieving search results: {e}")
            if len(results) < 1:
                break
            del results[:]
            page += 1

        parser.close()

    def download_torrent(self, url):
        f, path = mkstemp(".torrent")

        try:
            with self.session.open(url) as response:
                file = open(f, "wb")
                file.write(response.read())
                file.close()
        except Exception as e:
            print(f"Error downloading torrent: {e}")

        print(f"{path} {url}")
