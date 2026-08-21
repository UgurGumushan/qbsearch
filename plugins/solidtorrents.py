# VERSION: 1.0
"""
Solid Torrents (https://solidtorrents.to) search engine. Scrapes search pages
with a stateful HTML parser (size/seeds/leech are picked by column position
inside the stats div) and paginates at 20 results per page.
"""

import math
import re
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


class solidtorrents:
    url = "https://solidtorrents.to"
    name = "Solid Torrents"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    results_regex = r"<b>\d+<\/b>"

    class MyHtmlParser(HTMLParser):
        def error(self, message):
            pass

        LI, DIV, H5, A = ("li", "div", "h5", "a")

        def __init__(self, url: str):
            HTMLParser.__init__(self)
            self.magnet_regex = r'href=["\']magnet:.+?["\']'

            self.url = url
            self.row: dict[str, str] = {}

            self.column = 0

            self.insideSearchResult = False
            self.insideInfoDiv = False
            self.insideName = False
            self.shouldGetName = False
            self.insideStatsDiv = False
            self.insideStatsColumn = False
            self.insideLinksDiv = False

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            cssClasses = params.get("class") or ""
            if tag == self.LI and "search-result" in cssClasses:
                self.insideSearchResult = True
                return

            if self.insideSearchResult and tag == self.DIV and "info" in cssClasses:
                self.insideInfoDiv = True
                return

            if self.insideInfoDiv and tag == self.H5:
                self.insideName = True
                return

            if self.insideName and tag == self.A:
                self.shouldGetName = True
                href = params.get("href")
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                return

            if self.insideSearchResult and tag == self.DIV and "stats" in cssClasses:
                self.insideStatsDiv = True
                return

            if self.insideStatsDiv and tag == self.DIV:
                self.insideStatsColumn = True
                self.column += 1
                return

            if self.insideSearchResult and tag == self.DIV and "links" in cssClasses:
                self.insideLinksDiv = True
                return

            if self.insideLinksDiv and tag == self.A and "dl-magnet" in cssClasses:
                href = params.get("href")
                if href is not None:
                    self.row["link"] = href
                self.insideLinksDiv = False
                return

        def handle_data(self, data):
            if self.shouldGetName:
                self.row["name"] = data.strip()
                self.shouldGetName = False
                return

            if self.insideStatsDiv:
                if data.rstrip() != "":
                    if self.column == 2:
                        self.row["size"] = data.replace(" ", "")
                    if self.column == 3:
                        self.row["seeds"] = data
                    if self.column == 4:
                        self.row["leech"] = data
                return

        def handle_endtag(self, tag):
            if tag == self.H5 and self.insideName:
                self.insideName = False
                return

            if self.insideStatsDiv and not self.insideStatsColumn:
                self.insideStatsDiv = False
                self.insideInfoDiv = False
                return

            if self.insideStatsColumn and tag == self.DIV:
                self.insideStatsColumn = False
                return

            if tag == self.LI and self.insideSearchResult:
                self.row["engine_url"] = self.url
                print(self.row)
                _qbt_prettyPrinter(
                    SearchResults(
                        link=self.row["link"],
                        name=self.row["name"],
                        size=self.row["size"],
                        seeds=int(self.row["seeds"]),
                        leech=int(self.row["leech"]),
                        engine_url=self.row["engine_url"],
                        desc_link=self.row["desc_link"],
                    )
                )
                self.insideSearchResult = False
                self.column = 0
                return

    def download_torrent(self, info: str):
        print(download_file(info))

    def search(self, what, cat="all"):
        parser = self.MyHtmlParser(self.url)
        what = what.replace("%20", "+")
        what = what.replace(" ", "+")
        page = 1

        page_url = f"{self.url}/search?q={what}&page={page}"
        retrievedHtml = retrieve_url(page_url)
        results_matches = re.finditer(self.results_regex, retrievedHtml, re.MULTILINE)
        results_array = [x.group() for x in results_matches]

        if len(results_array) > 0:
            results = int(results_array[0].replace("<b>", "").replace("</b>", ""))
            pages = math.ceil(results / 20)
        else:
            pages = 0

        page += 1

        if pages > 0:
            parser.feed(retrievedHtml)

            while page <= min(pages, MAX_PAGES):
                page_url = f"{self.url}/search?q={what}&page={page}"
                retrievedHtml = retrieve_url(page_url)
                parser.feed(retrievedHtml)
                page += 1
        parser.close()
