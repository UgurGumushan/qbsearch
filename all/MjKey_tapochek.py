# VERSION: 1.1
# AUTHORS: MjKey
#
# Tapochek.net search engine plugin for qBittorrent
# The base of the plugin from imDMG

import base64
import json
import logging
import re
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Optional
from urllib.error import URLError, HTTPError
from urllib.parse import unquote, quote, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, ProxyHandler

import socks

try:
    from novaprinter import prettyPrinter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    from novaprinter import prettyPrinter

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.stem
FILE_J, FILE_C, FILE_L = [BASEDIR / (FILENAME + fl)
                          for fl in (".json", ".cookie", ".log")]

# regex for parsing rows in table#tor-tbl
RE_TORRENTS = re.compile(
    r'<tr[^>]*id="tor_(?P<tor_id>\d+)"[^>]*>.*?'
    r'<a[^>]*class="genmed"[^>]*href="\.\/viewtopic\.php\?t=(?P<topic_id>\d+)"[^>]*>'
    r'(?:<img[^>]*>\s*&nbsp;)?(?P<name>.+?)</a>.*?'
    r'<a[^>]*class="small tr-dl"[^>]*href="\./download\.php\?id=(?P<dl_id>\d+)">(?P<size_text>[\d\.,&nbsp;KMGTBkmg]+)</a>.*?'
    r'<td[^>]*class="row4 seedmed"[^>]*>\s*<b>(?P<seeds>[-\d]+)</b>.*?'
    r'<td[^>]*class="row4 leechmed"[^>]*>\s*<b>(?P<leech>[-\d]+)</b>.*?'
    r'<td[^>]*class="row4 small nowrap"[^>]*>\s*<u>(?P<pub_date>\d+)</u>',
    re.S | re.I
)

RE_RESULTS = re.compile(r'Результатов\sпоиска:\s(\d{1,6})', re.S)
PATTERNS = ("%stracker.php?nm=%s&%s", "%s&start=%s")

PAGES = 50

ICON = ("iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAC10lEQVQ4jW2TX4hVZRTFf3t/3zn3zFznoolNTTkTZmH/KLKoFB9KJIViKAQftKiXoOjFgsweTJrIl+qhIhBDE6awEjQfJCkoh3DSdAxTuoMpaJZ0G6f5c2fm3nvO+XYPd7oYtNl7v63F2ou15ZbV/cteePr6/kVdnV15MINm/29Jc8XO6adfDR3xhesel50HBitzOuYv2DdwlkLsUBFUBBNBrAlq0hpmhgVjqpayY9OjPPHS9o/9rTdeW9qye4jRao3IKyqKSFNE5BxZCAhgZoRZgompOnu/Heaum7sXax7Miu0R7YWIQhyThoAhjE2lHH5vLZvX38/kTEpmYAhJIWpNnofgMSNyHvWOPAQObuvl4LELtCceFWHlvQs5/cgSepcv4syFEd794iTeO1QVDLwBLlK8E8wc5/6c5NnVt7d8KyYRr224D4Avj5wniT01yVEVABTAqeLV8Xe1zsRkA4CJqTqbPhrkwwM/t8guXZmmWsuJnLYIPICqUOpI+Pz1NczrKACwedePXKxUOTr8F92dJR57oIf3X1xB+eIoG7Z9g4hiGIqBU4cIVMamWxkoFWNEFXWOYuIBqDUyKuM14mhWQcsDrzRmAs+8M8Cr6+6h96Ee3nhqKbu+PkvX/HYevvsGAF7e/gPnLo8zb04bKled4ETw6lkw13PnTXMBiLzjuTVL/hPEZXd0cnlsmkYjZxaPgiEqiAqxF9LM2HFomE++Ow9AtZbSt+cUg+UKUeRwIqiCXK1AVHAqFGLPlv4hkkJMPQ30PtjN0fII5Uvj/PLbKCFAWxLRyHL+leC9czpTz6inATQQRw6nQqkYs3HnCQxoSzxpQ0gtI00D9TSQZQGneH+8/MfIK+uWdg2c+p0k8TjncE5b2QgELA+kWSC3QJ4GZhoZTy7voe/Nt38V9JpVz2/94K3bFnd35nlmACKGMftRAgTBNCCmIM3o79l/6KfvP+vb+A+G/CMLnWXurwAAAABJRU5ErkJggg==")

# setup logging
logging.basicConfig(
    filemode="w",
    filename=FILE_L,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=logging.DEBUG,
)

logger = logging.getLogger(__name__)


def rng(t: int) -> range:
    return range(PAGES, -(-t // PAGES) * PAGES, PAGES)


class EngineError(Exception):
    ...


@dataclass
class Config:
    username: str = "USERNAME"
    password: str = "PASSWORD"
    cookies: str = "COOKIES"
    proxy: bool = False
    proxies: dict = field(default_factory=lambda: {"http": "", "https": ""})
    ua: str = ("Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 "
               "Firefox/38.0 ")

    def __post_init__(self):
        try:
            if not self._validate_json(json.loads(FILE_J.read_text())):
                raise ValueError("Incorrect json scheme.")
        except Exception as e:
            logger.error(e)
            FILE_J.write_text(self.to_str())
            (BASEDIR / f"{FILENAME}.ico").write_bytes(base64.b64decode(ICON))

    def to_str(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    def to_dict(self) -> dict:
        return {self._to_camel(k): v for k, v in self.__dict__.items()}

    def _validate_json(self, obj: dict) -> bool:
        is_valid = True
        for k, v in self.__dict__.items():
            _val = obj.get(self._to_camel(k))
            if type(_val) is not type(v):
                is_valid = False
                continue
            if type(_val) is dict:
                for dk, dv in v.items():
                    if type(_val.get(dk)) is not type(dv):
                        _val[dk] = dv
                        is_valid = False
            setattr(self, k, _val)
        return is_valid

    @staticmethod
    def _to_camel(s: str) -> str:
        return "".join(x.title() if i else x
                       for i, x in enumerate(s.split("_")))


config = Config()


class Tapochek:
    name = "Tapochek"
    url = "https://tapochek.net/"
    url_dl = url + "download.php?id="
    supported_categories = {"all": "-1"}  # not used, but kept for compatibility

    # cookies
    mcj = MozillaCookieJar()
    # establish connection
    session = build_opener(HTTPCookieProcessor(mcj))

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def download_torrent(self, url: str) -> None:
        self._catch_errors(self._download_torrent, url)

    def login(self) -> None:
        """
        Try cookies from config first, if not - attempt login with username/password.
        After that save cookies to local .cookie file.
        """
        # clear local in-memory jar
        self.mcj.clear()

        # try cookies string from config
        if config.cookies != "COOKIES" and config.cookies:
            for cookie in config.cookies.split("; "):
                if "=" not in cookie:
                    continue
                name, value = cookie.split("=", 1)
                # domain set to tapochek.net
                self.mcj.set_cookie(Cookie(
                    0, name, value, None, False, "tapochek.net", True, False,
                    "/", True, False, None, False, None, None, {}
                ))
            logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
            # quick check
            if self._check_login_page():
                self.mcj.save(str(FILE_C), ignore_discard=True, ignore_expires=True)
                logger.info("We successfully authorized with provided cookies")
                return

        # if cookies not valid or not provided, use username/password POST
        if config.username == "USERNAME" and config.password == "PASSWORD":
            raise EngineError("Empty credentials in config file")

        # prepare POST
        form = {
            "login_username": config.username,
            "login_password": config.password,
            "autologin": "1",
            "login": "Вход"
        }
        data = urllib.parse.urlencode(form, encoding="cp1251").encode()
        logger.debug(f"Login. Data before: {form}")
        # request login page
        resp = self.session.open(self.url + "login.php", data)
        logger.debug(f"Login response URL: {resp.geturl()}")
        # check login
        if not self._check_login_page():
            logger.debug(f"Cookies after login attempt: {[cookie for cookie in self.mcj]}")
            raise EngineError("We not authorized, please check your credentials!")
        self.mcj.save(str(FILE_C), ignore_discard=True, ignore_expires=True)
        logger.info("We successfully authorized")

    def _check_login_page(self) -> bool:
        try:
            page = self._request(self.url).decode("cp1251", "ignore")
            return "ucp.php?mode=logout" in page or "Выход" in page
        except Exception:
            return False

    def searching(self, query: str, first: bool = False) -> int:
        page, torrents_found = self._request(query).decode("cp1251", "ignore"), -1
        if first:
            # check login status already done in login
            match = RE_RESULTS.search(page)
            # optional: if RE_RESULTS not found, still try to parse rows
            if match is None:
                # if no explicit results counter - set unknown (-1) but continue parsing
                logger.debug("Results counter not found, will try to parse page")
                torrents_found = -1
            else:
                torrents_found = int(match.group(1))
                if torrents_found <= 0:
                    return 0
        self.draw(page)
        return torrents_found

    def draw(self, html: str) -> None:
        TAG_RE = re.compile(r'<[^>]+>')
        for tor in RE_TORRENTS.finditer(html):
            try:
                tor_id = tor.group("tor_id")
                name = unescape(TAG_RE.sub("",tor.group("name"))).strip()
                dl_id = tor.group("dl_id")
                link = self.url_dl + dl_id if dl_id else self.url
                size_text = tor.group("size_text").replace("&nbsp;", " ").strip()
                seeds = int(tor.group("seeds"))
                leech = int(tor.group("leech"))
                pub_date = int(tor.group("pub_date")) if tor.group("pub_date") else int(time.time())

                prettyPrinter({
                    "link": link,
                    "name": name,
                    "size": size_text,
                    "seeds": seeds,
                    "leech": leech,
                    "engine_url": self.url,
                    "desc_link": f"{self.url}viewtopic.php?t={tor.group('topic_id')}",
                    "pub_date": int(time.mktime(time.localtime(int(pub_date))))
                })
            except Exception as e:
                logger.exception("Failed to parse torrent row: %s", e)

    def _catch_errors(self, handler: Callable, *args: str):
        try:
            self._init()
            handler(*args)
        except EngineError as ex:
            logger.exception(ex)
            self.pretty_error(args[0], str(ex))
        except Exception as ex:
            self.pretty_error(args[0] if args else "", "Unexpected error, please check logs")
            logger.exception(ex)

    def _init(self) -> None:
        # add proxy handler if needed
        if config.proxy:
            if not any(config.proxies.values()):
                raise EngineError("Proxy enabled, but not set!")
            # socks5 support
            for proxy_str in config.proxies.values():
                if not proxy_str:
                    continue
                if not proxy_str.lower().startswith("socks"):
                    continue
                url = urlparse(proxy_str)
                socks.set_default_proxy(
                    socks.PROXY_TYPE_SOCKS5,
                    url.hostname,
                    url.port,
                    True,
                    url.username,
                    url.password
                )
                socket.socket = socks.socksocket  # type: ignore
                break
            else:
                self.session.add_handler(ProxyHandler(config.proxies))
            logger.debug("Proxy is set!")

        # change user-agent
        self.session.addheaders = [("User-Agent", config.ua)]

        # load local cookies
        try:
            self.mcj.load(str(FILE_C), ignore_discard=True)
            # quick check for some session cookie presence
            if any("bb" in cookie.name or "phpbb" in cookie.name or "session" in cookie.name for cookie in self.mcj):
                return logger.info("Local cookies loaded")
            logger.info("Local cookies expired or bad, try to login")
            logger.debug(f"That we have: {[cookie for cookie in self.mcj]}")
        except FileNotFoundError:
            logger.info("Local cookies not exists, try to login")
        # perform login procedure
        return self.login()

    def _search(self, what: str, cat: str = "all") -> None:
        c = self.supported_categories.get(cat, "-1")
        query = PATTERNS[0] % (self.url, quote(unquote(what)), "f=-1" if c == "-1" else "c=" + c)

        # first request
        t0, total = time.time(), self.searching(query, True)

        # if results are more than page size - request more in parallel
        if total and total > PAGES:
            qrs = [PATTERNS[1] % (query, x) for x in rng(total)]
            with ThreadPoolExecutor(len(qrs)) as executor:
                executor.map(self.searching, qrs, timeout=30)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def _download_torrent(self, url: str) -> None:
        response = self._request(url)

        with NamedTemporaryFile(suffix=".torrent", delete=False) as fd:
            fd.write(response)
            logger.debug(fd.name + " " + url)
            print(fd.name + " " + url)

    def _request(
        self,
        url: str,
        data: Optional[bytes] = None,
        repeated: bool = False,
    ) -> bytes:
        try:
            with self.session.open(url, data, 5) as r:
                # checking that tracker isn't blocked
                if r.geturl().startswith((self.url, self.url_dl)):
                    return r.read()
                raise EngineError(f"{url} is blocked. Try another proxy.")
        except (URLError, HTTPError) as err:
            logger.debug(err)
            error = str(getattr(err, "reason", err))
            reason = f"{url} is not response! Maybe it is blocked."
            if "timed out" in error:
                if not repeated:
                    logger.debug("Request timed out. Repeating...")
                    return self._request(url, data, True)
                reason = "Request timed out"
            if "no host given" in error:
                reason = "Proxy is bad, try another!"
            elif hasattr(err, "code"):
                reason = f"Request to {url} failed with status: {err.code}"

            raise EngineError(reason)

    def pretty_error(self, what: str, error: str) -> None:
        prettyPrinter({
            "engine_url": self.url,
            "desc_link": f"file://{FILE_L}",
            "name": f"[{unquote(what)}][Error]: {error}",
            "link": self.url + "error",
            "size": "1 TB",
            "seeds": 100,
            "leech": 100,
            "pub_date": int(time.time())
        })


# pep8
tapochek = Tapochek

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        EngineSettingsGUI(FILENAME)
    engine = tapochek()
    engine.search("doctor")



