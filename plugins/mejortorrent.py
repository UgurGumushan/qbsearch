# VERSION: 1.01
"""
MejorTorrent (Spanish) movies and series search. Scrapes the paginated search
results, then fetches each item page: films link their .torrent file directly,
series link their season page. Downloads are password-protected, the key
shown per episode.
"""

from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url  # noqa: F401
from novaprinter import SearchResults, prettyPrinter

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


_qbt_retrieve_url = globals().get("_qbt_helper_retrieve_url")


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


PLUGIN_MAX_PAGES = 10


class mejortorrent:
    url = "https://www36.mejortorrent.eu"
    name = "MejorTorrent"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "pelicula",
        "tv": "serie",
    }

    class SeriesHtmlParser(HTMLParser):
        def __init__(self, domain: str) -> None:
            HTMLParser.__init__(self)
            self.domain = domain
            self.path = ""
            self.title = ""
            self.title_found = False
            self.table_found = False
            self.item_found = False
            self.field_found = False
            self.key_found = False
            self.column_number = 0
            self.episode: str | None = None
            self.date: int | None = None
            self.key: str | None = None
            self.link: str | None = None

        def init(self, link: str) -> None:
            self.path = link
            self.title = ""
            self.title_found = False
            self.table_found = False
            self.item_found = False
            self.field_found = False
            self.key_found = False
            self.column_number = 0
            self.episode = None
            self.date = None
            self.key = None
            self.link = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if tag == "p":
                if "class" in params and "text-blue-900" in (params["class"] or ""):
                    self.title_found = True
                elif self.field_found:
                    self.key_found = True
            if self.table_found:
                if tag == "tr":
                    self.item_found = True
                elif tag == "td":
                    self.field_found = True
                elif tag == "a" and self.field_found and "href" in params:
                    self.link = params["href"]
            else:
                if tag == "tbody":
                    self.table_found = True

        def handle_data(self, data: str) -> None:
            data = data.strip()
            if self.title_found:
                self.title = data
            if self.field_found:
                if self.column_number == 1:
                    self.episode = data
                elif self.column_number == 2:
                    self.date = round(datetime.timestamp(datetime.strptime(data, "%Y-%m-%d")))
                elif self.column_number == 3 and self.key_found:
                    self.key = data

        def handle_endtag(self, tag: str) -> None:
            if tag == "p":
                if self.title_found:
                    self.title_found = False
                elif self.key_found:
                    self.key_found = False
            if tag == "td" and self.field_found:
                self.field_found = False
                self.column_number += 1
            if tag == "tr" and self.item_found:
                # "Sin clave" ("no key") means the episode has no password
                episode = self.episode if self.episode is not None else ""
                link = self.link if self.link is not None else ""
                key = (
                    ", password: " + self.key
                    if self.key is not None and self.key != "Sin clave"
                    else ""
                )
                _qbt_prettyPrinter(
                    SearchResults(
                        name=f"{self.title} ({episode}){key}",
                        size=-1,
                        link=f"{self.domain}{link}",
                        desc_link=self.path,
                        engine_url=self.domain,
                        seeds=-1,
                        leech=-1,
                        pub_date=self.date if self.date is not None else 0,
                    )
                )
                self.item_found = False
                self.episode = None
                self.date = None
                self.key = None
                self.link = None
                self.column_number = 0

    def __init__(self) -> None:
        self.tv_parser = self.SeriesHtmlParser(self.url)

    def download_torrent(self, info: SearchResults) -> None:
        print(download_file(info["link"]))

    def search(self, what: str, cat: str = "all") -> None:
        # Search example: https://www21.mejortorrent.zip/busqueda?q=godzilla
        search_url = f"{self.url}/busqueda?q={what}"
        html = retrieve_url(search_url)
        items: list[str] = []
        items.extend(self.parse_page(html, cat))
        for p in range(2, min(self.get_num_pages(html), MAX_PAGES, PLUGIN_MAX_PAGES) + 1):
            # Search page example: https://www21.mejortorrent.zip/busqueda/page/3?q=paco
            search_url = f"{self.url}/busqueda/page/{p}?q={what}"
            html = retrieve_url(search_url)
            items.extend(self.parse_page(html, cat))

        for i in items:
            if self.supported_categories["movies"] in i:
                self.parse_film(i)
            elif self.supported_categories["tv"] in i:
                self.parse_tv_season(i)

    def get_num_pages(self, html: str) -> int:
        pages = re.findall(r'"go to page [0-9]+"', html)
        if not pages:
            return 1
        else:
            # map to array of integers and calculate max value
            return max([int(n.strip('"').split(" ")[-1]) for n in pages])

    def parse_page(self, html: str, category: str) -> list[str]:
        # copy minus the "all" entry (its value is the cat filter, not a slug)
        all_categories = {k: v for k, v in self.supported_categories.items() if k != "all"}
        category_patterns = (f'{self.url}/{e}/[0-9]+/[^"]+' for e in list(all_categories.values()))
        pattern = (
            r"({})".format("|".join(category_patterns))
            if category == "all"
            else rf"{self.url}/{self.supported_categories[category]}/[0-9]+/[^\"]+"
        )
        return re.findall(pattern, html)

    def parse_film(self, url: str) -> None:
        html = retrieve_url(url)
        title_match = re.search(r'text-blue-900">[^\<]+', html)
        title = title_match.group(0).split(">")[-1] if title_match else ""
        quality_match = re.search(r"/quality/[^\"]+", html)
        quality = quality_match.group(0).split("/")[-1] if quality_match else ""
        path_match = re.search(r"/torrents/.+\.torrent", html)
        date_match = re.search(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", html)
        pub_date = (
            round(datetime.timestamp(datetime.strptime(date_match.group(0), "%d/%m/%Y")))
            if date_match
            else 0
        )
        info: SearchResults = {
            "name": f"{title} ({quality})",
            "size": -1,
            "link": "{domain}{path}".format(
                domain=self.url, path=path_match.group(0) if path_match else ""
            ),
            "desc_link": url,
            "engine_url": self.url,
            "seeds": -1,
            "leech": -1,
            "pub_date": pub_date,
        }
        _qbt_prettyPrinter(info)

    def parse_tv_season(self, link: str) -> None:
        html = retrieve_url(link)
        self.tv_parser.init(link)
        self.tv_parser.feed(html)
