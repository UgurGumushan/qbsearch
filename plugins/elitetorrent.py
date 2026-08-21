# VERSION: 1.6
"""Elitetorrent (Spanish) engine: movie and TV series torrents.

The magnet link stored on each torrent page is obfuscated with repeated
Base64 plus ROT13 layers, which this engine reverses before printing.
"""

from __future__ import annotations

import base64
import codecs
import re
from datetime import datetime
from typing import ClassVar, TypedDict, cast

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
    from types import TracebackType as _QBTTracebackType
    from typing import Callable as _QBTCallable
    from typing import Protocol as _QBTProtocol
    from typing import TypeVar as _QBTTypeVar
    from typing import cast as _qbt_cast
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
_qbt_search_deadline: float | None = None
_QBTJobResult = _QBTTypeVar("_QBTJobResult")


class _QBTResponse(_QBTProtocol):
    status: int | None

    def close(self) -> None: ...

    def read(self, *args: object, **kwargs: object) -> bytes: ...

    def getcode(self) -> int: ...

    def geturl(self) -> str: ...

    def getheader(self, name: str, default: object = None) -> object: ...

    def info(self) -> _QBTResponse: ...

    def get(self, name: str, default: object = None) -> object: ...


class _QBTResponseContext(_QBTResponse, _QBTProtocol):
    def __enter__(self) -> _QBTResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool: ...


_qbt_urlopen_typed = _qbt_cast(_QBTCallable[..., _QBTResponseContext], _qbt_urlopen)


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status: int | None = 200
    code: int = 200
    _url: str

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: _QBTTracebackType | None,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *_args: object, **_kwargs: object) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, _name: str, default: object = None) -> object:
        return default

    def info(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def get(self, _name: str, default: object = None) -> object:
        return default


def _qbt_empty_response(url: object) -> _QBTResponseContext:
    return _qbt_cast(_QBTResponseContext, _qbt_cast(object, _QBTEmptyResponse(url)))


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result: object = operation()
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


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen_typed(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _qbt_empty_response(url)
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
            return _qbt_empty_response(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _qbt_empty_response(url)


_qbt_retrieve_url = _qbt_cast(_QBTCallable[..., object], _qbt_helper_retrieve_url)


def retrieve_url(*args: object, **kwargs: object) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result: object) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        printer = _qbt_cast(_QBTCallable[[object], None], prettyPrinter)
        printer(result)


def _qbt_run_parallel(
    worker: _QBTCallable[..., _QBTJobResult],
    jobs: _QBTIterable[object],
    deadline: float | None = None,
) -> list[_QBTJobResult]:
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures: list[_QBTFuture[_QBTJobResult]] = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results: list[_QBTJobResult] = []
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
            _ = future.cancel()
    finally:
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            _ = executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# These hooks are available to standalone engines even when a particular
# engine does not call every optional adapter directly.
__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


MAX_DEPTH = 10  # Safety cap on how many Base64+ROT13 layers to peel off.


class TorrentInfo(TypedDict):
    title: str | None
    link: list[str] | str | None
    size: str
    quality: str | None
    language: str | None
    date: str | int
    seeds: str | int
    leech: str | int
    formatted_name: str


def deobfuscate_magnet(obfuscated: str) -> str | None:
    encoded = obfuscated.encode()
    try:
        for _ in range(MAX_DEPTH):
            decoded_bytes = base64.b64decode(encoded)
            decoded_value = codecs.decode(decoded_bytes.decode(encoding="utf-8"), "rot_13")
            if "magnet" in decoded_value:
                return decoded_value
            encoded = decoded_bytes
    except Exception:
        return None
    return None


def format_info(info: TorrentInfo) -> None:
    links = info["link"]
    if isinstance(links, list):
        # The site normally includes a second matching attribute; accept the
        # first one as a safe fallback when a page contains only one.
        encoded_link = links[1] if len(links) > 1 else links[0] if links else None
        info["link"] = (
            deobfuscate_magnet(encoded_link.lstrip("i=").rstrip('"'))
            if encoded_link is not None
            else None
        )
    else:
        info["link"] = None

    title = info["title"] or ""
    if title.startswith("<h1>") and title.endswith("</h1>"):
        title = title[4:-5]
    if title.startswith("Descargar ") and title.endswith(" por torrent"):
        title = title[10:-12].strip()

    formatted_name = title
    if info["language"] is not None:
        formatted_name += " [{}]".format(info["language"])
    if info["quality"] is not None:
        formatted_name += " {} ".format(info["quality"])
    formatted_name += "({})".format(info["date"])
    info["formatted_name"] = formatted_name


class elitetorrent:
    url: str = "https://www.elitetorrent.com"
    name: str = "Elitetorrent"
    # Page has only movies and tv series. Search box has no filters
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "peliculas",
        "tv": "series",
    }

    def __init__(self) -> None:
        self.pages_limit: int = 2  # Limit of pages, more pages increase the time it takes

    def download_torrent(self, info: SearchResults) -> None:
        """Unused: results already carry ready-to-use magnet links."""
        print(download_file(info["link"]))

    def search(self, what: str, cat: str = "all") -> None:
        search_url = "{}/?s={}".format(self.url, what.replace("%20", "+"))
        html = retrieve_url(search_url)

        # Get number of pages
        number_pages = 0
        if "paginacion" in html:
            pages = cast(list[str], re.findall(r'<a.*?class="pagina.*?</a>', html))
            if len(pages) > 0:
                last_page = pages[-1]
                last_page = cast(list[str], re.findall(r"page/.*?/", last_page))[0]
                last_page = last_page.replace("/", "").replace("page", "")
                number_pages = int(last_page)

        # Only one page but there are results
        elif "Resultado de buscar" in html:
            number_pages = 1
        else:
            # No pagination links and no single-results banner: nothing found.
            number_pages = 0

        # Set number of pages depending by limit
        number_pages = min(self.pages_limit, number_pages)

        links: list[str] = []

        for page in range(1, min(number_pages, MAX_PAGES) + 1):
            # Page urls look like: {url}/page/{n}/?s={query}
            url = "{}/page/{}/?s={}".format(self.url, page, what.replace("%20", "+"))
            html = retrieve_url(url).replace("\n", "")  # Replace newline to help the regex
            # I hate regex, check if selected category is films or tv, if its 'all' get both
            pattern = (
                rf"({self.url}/series/.*?/|{self.url}/peliculas/.*?/)"
                if cat == "all"
                else rf"{self.url}/{self.supported_categories[cat]}/.*?/"
            )
            # Collect every matching result link on the page.
            items = cast(list[str], re.findall(pattern, html))
            for result_link in items:
                if result_link not in links:
                    links.append(result_link)

        for i in links:
            # Visiting individual results to get its attributes makes it so slow
            data = retrieve_url(i).replace("\n", "")
            info: TorrentInfo = {
                "title": None,
                "link": [],
                "size": "0",
                "quality": None,
                "language": None,
                "date": -1,
                "seeds": -1,
                "leech": -1,
                "formatted_name": "",
            }
            m_title = re.search(r"<h1>Descargar .+ por torrent</h1>", data)
            info["title"] = m_title.group(0) if m_title else None
            info["link"] = re.findall(r"i=[-A-Za-z0-9+/]+\={0,3}\"", data)
            m = re.search(r"Tama.?o:</b> [0-9\.]+[\ GM]+B", data)
            info["size"] = m.group(0).split("</b>")[1].strip() if m else "0"
            m = re.search(r"Calidad:</b> [0-9\.a-z\-]+", data)
            info["quality"] = m.group(0).removeprefix("Calidad:</b>").strip() if m else None
            m = re.search(r"Idioma:</b>[a-zA-Zñ\ ]+", data)
            info["language"] = m.group(0).removeprefix("Idioma:</b>").strip() if m else None
            m = re.search(r"Fecha:</b>[\ 0-9\-]+", data)
            info["date"] = m.group(0).replace(" ", "").removeprefix("Fecha:</b>") if m else -1
            m = re.search(r"<b>Semillas</b>:[\ 0-9]*", data)
            info["seeds"] = m.group(0).split(":")[-1].strip() if m else -1
            m = re.search(r"<b>Clientes</b>:[\ 0-9]*", data)
            info["leech"] = m.group(0).split(":")[-1].strip() if m else -1

            format_info(info)
            if info["title"] is None or not isinstance(info["link"], str):
                continue  # decoding has failed, skip

            pub_date = info["date"]
            if isinstance(pub_date, str):
                # there are 2 format dates: YYYY-MM-DD or DD-MM-YYYY
                if int(pub_date.split("-")[0]) > 1000:
                    parsed_date = datetime.strptime(pub_date, "%Y-%m-%d")
                else:
                    parsed_date = datetime.strptime(pub_date, "%d-%m-%Y")
                pub_date = round(datetime.timestamp(parsed_date))

            seeds = info["seeds"]
            leech = info["leech"]
            item: SearchResults = {
                "seeds": int(seeds)
                if isinstance(seeds, str) and seeds
                else seeds
                if isinstance(seeds, int)
                else -1,
                "leech": int(leech)
                if isinstance(leech, str) and leech
                else leech
                if isinstance(leech, int)
                else -1,
                "name": info["formatted_name"],
                "size": info["size"],
                "desc_link": i,
                "engine_url": self.url,
                "link": info["link"],
                "pub_date": pub_date,
            }
            # Prints in this format: link|name|size|seeds|leech|engine_url|desc_link|pub_date
            _qbt_prettyPrinter(item)
