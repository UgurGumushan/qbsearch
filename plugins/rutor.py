# VERSION: 1.21
"""
Rutor (https://rutor.info) search engine. Scrapes the Rutor multi-site
aggregator; optional http/https/socks5 proxy support is configured in
rutor.json, and large result sets are fetched concurrently one page at a time.
"""

# Rutor.org search engine plugin for qBittorrent
from __future__ import annotations

import base64
import json
import logging
import re
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import ProxyHandler, build_opener

_qbt_helper_retrieve_url = None
# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error

HTTP_TIMEOUT = 20.0
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.25
MAX_WORKERS = 4
SEARCH_DEADLINE = 60.0
MAX_PAGES = 30
MAX_DETAILS = 100

_qbt_socket.setdefaulttimeout(HTTP_TIMEOUT)
_QBT_RETRYABLE_HTTP_STATUS = frozenset((408, 425, 429, 500, 502, 503, 504))
_qbt_search_deadline = None


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status = 200
    code = 200

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *args, **kwargs) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, name: str, default: object = None):
        return default

    def info(self):
        return self

    def get(self, name: str, default: object = None):
        return default


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result = operation()
            if isinstance(result, str) and result:
                return result
            if result not in (None, "", b""):
                return str(result)
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return ""
            try:
                error.close()
            except Exception:
                pass
        except Exception:
            pass
        if attempt + 1 < max(1, int(MAX_ATTEMPTS)):
            _qbt_sleep(attempt)
    return ""


def _qbt_safe_urlopen(url, data=None, *, context=None):
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _QBTEmptyResponse(url)
        response = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status is not None and status >= 400:
                response.close()
                return _QBTEmptyResponse(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _QBTEmptyResponse(url)
            try:
                error.close()
            except Exception:
                pass
        except (_QBTTransientHTTPError, OSError, EOFError, TimeoutError):
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
        except Exception:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            # A malformed request is not useful to retry, but it must not
            # abort the qBittorrent search process.
            return _QBTEmptyResponse(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _QBTEmptyResponse(url)


_qbt_retrieve_url = _qbt_helper_retrieve_url


def retrieve_url(*args, **kwargs) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        prettyPrinter(result)


def _qbt_run_parallel(worker, jobs, deadline=None):
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results = []
    try:
        remaining = max(0.0, deadline - _qbt_time.monotonic())
        for future in _qbt_as_completed(futures, timeout=remaining):
            try:
                results.append(future.result())
            except Exception:
                # One dead site/detail page must not discard other results.
                pass
    except _qbt_FuturesTimeoutError:
        for future in futures:
            future.cancel()
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# END GENERATED QBITT SAFETY PREAMBLE


try:
    import socks
    from novaprinter import prettyPrinter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
    import socks
    from novaprinter import prettyPrinter

FILE = Path(__file__)
BASEDIR = FILE.parent.absolute()

FILENAME = FILE.stem
FILE_J, FILE_C, FILE_L = [
    BASEDIR / (FILENAME + fl) for fl in (".json", ".cookie", ".log")
]

RE_TORRENTS = re.compile(
    r'(?:gai|tum)"><td>(?P<pub_date>.+?)</td.+?href="(?P<mag_link>magnet:'
    r'.+?)".+?href="/(?P<desc_link>torrent/(?P<tor_id>\d+).+?)">(?P<name>.+?)'
    r'</a.+?right">(?P<size>[.\d]+?&nbsp;\w+?)</td.+?<span.+?(?P<seeds>\d+?)'
    r"</span>.+?<span.+?(?P<leech>\d+?)</span>",
    re.DOTALL,
)
RE_RESULTS = re.compile(r"</b>\sРезультатов\sпоиска\s(\d{1,4})\s", re.DOTALL)
PATTERNS = ("%ssearch/%i/%i/000/0/%s",)

PAGES = 100

# base64 encoded image
ICON = (
    "AAABAAEAEBAAAAEAGABoAwAAFgAAACgAAAAQAAAAIAAAAAEAGAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAc4AAMwHNdcQ4vsN3fYS2fUY3fUe3fMj4fkk4fco4PYo5fgk7f5gp8ZuZZtsa5"
    "9FIXZEGm4kh74PyeoLGp8NHK4PHrwQHr8VIb8XJL4bJrUcKJ8optEdtPMBGcQAIcXeZAPVYwd"
    "A3MQFf8EDAJoFAMEEAM0AANIAAM4AAM0EAL8CAI8bXaEV1/cBHMsGDNTVWAOodTIU5/ELuOAJ"
    "M6sEALsIAMoEALkCBbgFALUGAKshgMcvpNUTzOoFQNIFANqxQgBpkmgKue8IT8UUy+8HO7MHP"
    "b8Gt+IG3vQHm9YKi84X4foKI7kRl+AWiMwSDYyxjXZAy84HdNYEALcPguYM+vsL6PgGl/wBWN"
    "4K1/EF//8LbdQEALgEVc41zMp0YC+t0N0XxPcCIbwGAMkGGOUGUvQKPPUEANsIU9ENvvAJw/U"
    "LnekGAr8FJcIUzfRycEZwzuMFnuYEArQCAdYDANYHAMQFAMwGPcwM2vsHU/QKPegLwvYEEckF"
    "BrsOt/Y+kYky5/YGgNAGAKkHAc4JMssSoN0GTb0L2/gHYPkCAPkFKOMP0fIHGc0EAKwLgNAq3"
    "OMd/P0Al9ACBqQCAMALbOMG+/8E8v0KjugBAO4CAPAGQ9MNyPYEB8QBAKQCe8cW9//T+/09+/"
    "8Aqd8GIbIFAMAKbuUG6f8Ht/IFFeEAAMYPqeYMhOEGB6oCgtUY5fuG0tv//vzs+PlQ9fwAw+4"
    "CLLoIALgJR+EFU+wEFcweZNAkquMFMrkArOor4fSrxsvWx8n5/fv5+fn3+/iC8fsLzPIAUscE"
    "ALMDAL8QPtAsetUFWsUHue1r7/vc6evOzMfFx8n5/fvy+fj89vb/9/e+9/o44/oNi9kBD54CF"
    "KQJg9Qu4vu09vr/+ff89fTIz8rFx8n5/fvy+fj59vb49vf/+fbh+vtk6vw1rN03suFn6vnl/f"
    "3/+fn49vj18/TIz8rFx8n5/fvy+fj59vb39vf39/f//P3w+fme6/ak8Prv+fj//f369/r39vj"
    "18/TIz8rFx8ngBwAA4AMAAMADAADAAwAAwAMAAMABAACAAQAAgAEAAAAAAAAAAAAAgAEAAMAD"
    "AADgBwAA+B8AAPw/AAD+fwAA"
)

# setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(FILE_L, mode="w")
_fh.setFormatter(logging.Formatter(
    fmt="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
))
logger.addHandler(_fh)
logger.propagate = False


def rng(t: int) -> range:
    return range(1, -(-t // PAGES))


def date_normalize(date_str: str) -> int:
    # Map Russian month abbreviations (Янв, Фев, ...) to month numbers.
    months = (
        "Янв",
        "Фев",
        "Мар",
        "Апр",
        "Май",
        "Июн",
        "Июл",
        "Авг",
        "Сен",
        "Окт",
        "Ноя",
        "Дек",
    )
    date_str = next(
        date_str.replace(m, f"{i:02d}")
        for i, m in enumerate(months, 1)
        if m in date_str
    )
    return int(time.mktime(time.strptime(date_str, "%d %m %y")))


class EngineError(Exception): ...


@dataclass
class Config:
    # username: str = "USERNAME"
    # password: str = "PASSWORD"
    magnet: bool = False
    proxy: bool = False
    # dynamic_proxy: bool = True
    proxies: dict[str, str] = field(
        default_factory=lambda: {"http": "", "https": ""}
    )
    ua: str = (
        "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0 "
    )

    def __post_init__(self) -> None:
        try:
            if not self._validate_json(json.loads(FILE_J.read_text())):
                raise ValueError("Incorrect json scheme.")
        except Exception as e:
            logger.error(e)
            _ = FILE_J.write_text(self.to_str())
            _ = (BASEDIR / f"{FILENAME}.ico").write_bytes(base64.b64decode(ICON))

    def to_str(self) -> str:
        return json.dumps(self.to_dict(), indent=4, sort_keys=False)

    def to_dict(self) -> dict[str, Any]:
        return {self._to_camel(k): v for k, v in self.__dict__.items()}

    def _validate_json(
        self, obj: dict[str, str | bool | dict[str, str]]
    ) -> bool:
        is_valid = True
        for k, v in self.__dict__.items():
            _val = obj.get(self._to_camel(k))
            if _val is None or not isinstance(_val, type(v)):
                is_valid = False
                continue
            if isinstance(_val, dict):
                for dk, dv in v.items():
                    if not isinstance(_val.get(dk), type(dv)):
                        _val[dk] = dv
                        is_valid = False
            setattr(self, k, _val)
        return is_valid

    @staticmethod
    def _to_camel(s: str) -> str:
        return "".join(
            x.title() if i else x for i, x in enumerate(s.split("_"))
        )


config = Config()


class Rutor:
    name = "Rutor"
    url = "https://rutor.info/"
    url_dl = url.replace("//", "//d.") + "download/"
    supported_categories: ClassVar[dict[str, int]]  = {
        "all": 0,
        "movies": 1,
        "tv": 6,
        "music": 2,
        "games": 8,
        "anime": 10,
        "software": 9,
        "pictures": 3,
        "books": 11,
    }

    # establish connection
    session = build_opener()

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def download_torrent(self, url: str) -> None:
        self._catch_errors(self._download_torrent, url)

    def searching(self, query: str, first: bool = False) -> int:
        page, torrents_found = self._request(query).decode(), -1
        if first:
            # firstly, we check if there is a result
            match = RE_RESULTS.search(page)
            if match is None:
                logger.debug(f"Unexpected page content:\n {page}")
                raise EngineError("Unexpected page content")
            torrents_found = int(match[1])
            if torrents_found <= 0:
                return 0
        self.draw(page)

        return torrents_found

    def draw(self, html: str) -> None:
        for tor in RE_TORRENTS.finditer(html):
            _qbt_prettyPrinter(
                {
                    "link": (
                        tor.group("mag_link")
                        if config.magnet
                        else self.url_dl + tor.group("tor_id")
                    ),
                    "name": unescape(tor.group("name")),
                    "size": tor.group("size").replace("&nbsp;", " "),
                    "seeds": int(tor.group("seeds")),
                    "leech": int(tor.group("leech")),
                    "engine_url": self.url,
                    "desc_link": self.url + tor.group("desc_link"),
                    "pub_date": date_normalize(
                        unescape(tor.group("pub_date"))
                    ),
                }
            )

    def _catch_errors(self, handler: Callable[..., None], *args: str) -> None:
        try:
            self._init()
            handler(*args)
        except EngineError as ex:
            logger.exception("Engine error during search")
            self.pretty_error(args[0], str(ex))
        except Exception:
            self.pretty_error(args[0], "Unexpected error, please check logs")
            logger.exception("Unexpected error while searching")

    def _init(self) -> None:
        # add proxy handler if needed
        if config.proxy:
            if not any(config.proxies.values()):
                raise EngineError("Proxy enabled, but not set!")
            # socks5 support
            for proxy_str in config.proxies.values():
                if not proxy_str.lower().startswith("socks"):
                    continue
                url = urlparse(proxy_str)
                socks.set_default_proxy(
                    socks.PROXY_TYPE_SOCKS5,
                    url.hostname,
                    url.port,
                    True,
                    url.username,
                    url.password,
                )
                socket.socket = socks.socksocket
                break
            else:
                self.session.add_handler(ProxyHandler(config.proxies))
            logger.debug("Proxy is set!")

        # change user-agent
        self.session.addheaders = [("User-Agent", config.ua)]

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (
            self.url,
            0,
            self.supported_categories[cat],
            quote(unquote(what)),
        )

        # make first request (maybe it enough)
        t0, total = time.time(), self.searching(query, True)
        # do async requests
        if total > PAGES:
            query = query.replace("h/0", "h/{}")
            qrs = [query.format(x) for x in rng(total)][:MAX_PAGES]
            _qbt_run_parallel(self.searching, [(qr,) for qr in qrs], _qbt_new_deadline())

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def _download_torrent(self, url: str) -> None:
        # Download url
        response = self._request(url)

        # Create a torrent file
        with NamedTemporaryFile(suffix=".torrent", delete=False) as fd:
            _ = fd.write(response)

            # return file path
            logger.debug(fd.name + " " + url)
            print(fd.name + " " + url)

    def _request(
        self,
        url: str,
        data: bytes | None = None,
        repeated: bool = False,
    ) -> bytes:
        attempts = 1 if repeated else max(1, int(MAX_ATTEMPTS))
        for attempt in range(attempts):
            try:
                with self.session.open(url, data, HTTP_TIMEOUT) as r:
                    # check if the response is from the correct domain
                    if r.geturl().startswith((self.url, self.url_dl)):
                        return r.read()
                    raise EngineError(f"{url} is blocked. Try another proxy.")

            except HTTPError as err:
                raise EngineError(
                    f"Request to {url} failed with status: {err.code}"
                ) from err
            except (URLError, TimeoutError) as err:
                reason = getattr(err, "reason", None)
                if isinstance(reason, str) and reason == "no host given":
                    raise EngineError("Proxy is bad, try another!") from err

                is_timeout = isinstance(err, TimeoutError) or isinstance(
                    reason, TimeoutError
                )
                if attempt + 1 < attempts:
                    logger.debug("Request failed; repeating bounded attempt %s", attempt + 2)
                    _qbt_sleep(attempt)
                    continue

                if is_timeout:
                    raise EngineError(
                        f"{url} is not responding (timed out)."
                    ) from err
                raise EngineError(
                    f"{url} is not response! Maybe it is blocked."
                ) from err

        raise EngineError(f"{url} is not response! Maybe it is blocked.")

    def pretty_error(self, what: str, error: str) -> None:
        _qbt_prettyPrinter(
            {
                "engine_url": self.url,
                "desc_link": f"file://{FILE_L}",
                "name": f"[{unquote(what)}][Error]: {error}",
                "link": self.url + "error",
                "size": "1 TB",  # lol
                "seeds": 100,
                "leech": 100,
                "pub_date": int(time.time()),
            }
        )


# pep8
rutor = Rutor

if __name__ == "__main__":
    if BASEDIR.parent.joinpath("settings_gui.py").exists():
        from settings_gui import EngineSettingsGUI

        _ = EngineSettingsGUI(str(BASEDIR / FILENAME))
    engine = rutor()
    engine.search("doctor")
