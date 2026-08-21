# VERSION: 1.1
"""
TomaDivx (https://tomadivx.net, Spanish site) search engine. For each result
the engine fetches the detail page to pull out the .torrent link and the size
(labelled 'Tamaño:'); later pages are fetched concurrently in threads.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
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


class tomadivx:
    url = "https://tomadivx.net/"
    headers: ClassVar[dict[str, str]] = {
        "Referer": url
    }
    name = "TomaDivx"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    results_regex = r"<p.+?>Se han encontrado.+?<b>\d+</b>.+?resultados.+?</p>"

    class MyHtmlParser(HTMLParser):
        magnet_regex = r'href=["\'].+?\.torrent["\']'
        size_regex = r"<p.+?><b.+?>Tamaño:</b>.+?</p>"

        def error(self, message: str):
            pass

        DIV, P, A, SPAN = ("div", "p", "a", "span")

        def __init__(self, url: str):
            HTMLParser.__init__(self)

            self.url = url
            self.headers: dict[str, str] = {"Referer": url}
            self.row: dict[str, str] = {}
            self.name = ""
            self.seeds = -1
            self.leech = -1

            self.column = 0

            self.insideBuscadorDiv = False
            self.insideCardDiv = False
            self.insideCardBodyDiv = False
            self.insideResult = False
            self.insideResultSpan = False
            self.insideLink = False
            self.insideType = False
            self.insideBadge = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            cssClasses = params.get("class", "") or ""
            elementId = params.get("id", "")

            if tag == self.DIV and elementId == "buscador":
                self.insideBuscadorDiv = True
                return

            if self.insideBuscadorDiv and "card" in cssClasses and "card-body" not in cssClasses:
                self.insideCardDiv = True
                return

            if self.insideCardDiv and "card-body" in cssClasses:
                self.insideCardBodyDiv = True
                return

            if self.insideCardBodyDiv and tag == self.P and len(cssClasses) == 0:
                self.insideResult = True
                self.name = ""
                return

            if self.insideResult and not self.insideResultSpan and tag == self.SPAN:
                self.insideResultSpan = True
                return

            if self.insideResultSpan and tag == self.A:
                self.insideLink = True
                href = params.get("href")
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                self.row["link"] = link
                torrent_page: str = retrieve_url(link, self.headers)
                matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                magnet_urls = [x.group() for x in matches]
                self.row["link"] = "https:" + magnet_urls[0].split("'")[1]
                matches = re.finditer(self.size_regex, torrent_page, re.MULTILINE)
                size = [x.group() for x in matches]
                sizeEl = re.sub(r"<b.+?>Tamaño:</b>", "", size[0])
                root = ET.fromstring(sizeEl)
                self.row["size"] = (root.text or "").replace(",", ".")
                self.seeds = -1
                self.leech = -1
                return

            if self.insideResultSpan and tag == self.SPAN and len(cssClasses) == 0:
                self.insideType = True
                return

            if self.insideResultSpan and tag == self.SPAN and "badge" in cssClasses:
                self.insideBadge = True
                return

        def handle_data(self, data: str) -> None:
            if self.insideLink:
                self.name = data
                return

            if self.insideType:
                self.name += f" ({data})"
                return

            if self.insideBadge:
                self.name += f" [{data}]"
                return

        def handle_endtag(self, tag: str) -> None:
            if self.insideBadge and tag == self.SPAN:
                self.insideBadge = False
                return

            if self.insideType and tag == self.SPAN:
                self.insideType = False
                return

            if self.insideLink and tag == self.A:
                self.insideLink = False
                return

            if (
                self.insideResultSpan
                and not self.insideBadge
                and not self.insideType
                and tag == self.SPAN
            ):
                self.insideResultSpan = False
                return

            if self.insideResult and tag == self.P:
                res: SearchResults = {
                    "link": self.row["link"],
                    "name": self.name,
                    "size": self.row["size"],
                    "seeds": self.seeds,
                    "leech": self.leech,
                    "engine_url": self.url,
                    "desc_link": self.row["desc_link"],
                }
                _qbt_prettyPrinter(res)
                self.column = 0
                self.row = {}
                self.name = ""
                self.insideResult = False
                self.insideResultSpan = False
                return

            if self.insideCardBodyDiv and tag == self.DIV:
                self.insideCardBodyDiv = False
                return

            if self.insideCardDiv and self.insideCardBodyDiv is False and tag == self.DIV:
                self.insideCardDiv = False
                return

            if self.insideBuscadorDiv and self.insideCardDiv is False and tag == self.DIV:
                self.insideBuscadorDiv = False
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def get_page_url(self, what: str, page: int) -> str:
        return f"{self.url}/buscar/{what}/page/{page}"

    def threaded_search(self, page: int, what: str) -> None:
        page_url = self.get_page_url(what, page)
        headers = dict(self.headers)
        headers["Referer"] = page_url
        retrieved_html: str = retrieve_url(page_url, headers)
        parser = self.MyHtmlParser(self.url)
        parser.feed(retrieved_html)
        parser.close()

    def search(self, what: str, cat: str = "all") -> None:
        page = 1
        retrieved_html: str = retrieve_url(self.get_page_url(what, page), self.headers)
        matches = re.finditer(self.results_regex, retrieved_html, re.MULTILINE)
        results_el = [x.group() for x in matches]
        if not results_el:
            return
        root: ET.Element = ET.fromstring(results_el[0])
        results: str = root[0].text or "0"
        pages = math.ceil(int(results) / 10)

        parser = self.MyHtmlParser(self.url)
        parser.feed(retrieved_html)
        parser.close()

        page += 1

        jobs = [(p, what) for p in range(page, min(pages, MAX_PAGES) + 1)]
        _qbt_run_parallel(self.threaded_search, jobs, _qbt_new_deadline())
