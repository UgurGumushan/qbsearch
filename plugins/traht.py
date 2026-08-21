# VERSION: 1.0
"""
Traht (https://traht.org) search engine. Scrapes the releases table; the
peers cell may be formatted as "seeders|leechers" and is split on the pipe
accordingly. The last page number is read from the paginator_pages div.
"""

import re
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


class traht:
    url = "https://traht.org"
    name = "Traht"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    pagination_regex = r'<div class="paginator_pages">.*?<\/div>'

    class MyHtmlParser(HTMLParser):
        def error(self, message):
            pass

        DIV, TABLE, TBODY, TR, TD, A, SPAN, I, B = (
            "div",
            "table",
            "tbody",
            "tr",
            "td",
            "a",
            "span",
            "i",
            "b",
        )

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.magnet_regex = r'href=["\']magnet:.+?["\']'

            self.url = url
            self.row = self._new_row()

            self.column = 0

            self.releaseTableFound = False
            self.insideResultTbody = False
            self.insideRow = False
            self.insideCell = False

            self.shouldGetName = False
            self.shouldParseLink = True
            self.shouldGetSize = False
            self.shouldGetPeers = False
            self.shouldGetSeeds = False
            self.shouldGetLeechs = False

        def _new_row(self) -> SearchResults:
            return {
                "link": "",
                "name": "",
                "size": "",
                "seeds": 0,
                "leech": 0,
                "engine_url": self.url,
            }

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            elementId = params.get("id", "")

            if elementId == "releases-table":
                self.releaseTableFound = True
                return

            if self.releaseTableFound and elementId == "highlighted" and tag == self.TBODY:
                self.insideResultTbody = True
                return

            if self.insideResultTbody and tag == self.TR:
                self.insideRow = True
                self.column = 0
                return

            if self.insideRow and tag == self.TD:
                self.column += 1
                self.insideCell = True
                if self.column == 5:
                    self.shouldGetSize = True

                if self.column == 6:
                    self.shouldGetPeers = True

                if self.column == 7:
                    self.shouldGetPeers = False
                    self.shouldGetSeeds = False
                    self.shouldGetLeechs = False

                return

            if self.insideCell and self.column == 2 and tag == self.B:
                self.shouldGetName = True
                return

            if self.insideCell and self.column == 2 and tag == self.A:
                href = params.get("href")
                link = f"{self.url}/{href}"
                self.row["desc_link"] = link
                return

            if self.insideCell and self.column == 3 and tag == self.A and self.shouldParseLink:
                self.shouldParseLink = False
                href = params.get("href")
                link = f"{self.url}/{href}&ok="
                self.row["link"] = link
                return

            if self.column == 6 and tag == self.B and self.shouldGetSeeds:
                if not self.shouldGetSeeds:
                    self.shouldGetLeechs = True
                return

        def handle_data(self, data):
            if self.shouldGetName:
                self.row["name"] = data
                self.shouldGetName = False

            if self.shouldGetSize:
                self.row["size"] = data.replace(",", ".")
                self.shouldGetSize = False

            if self.shouldGetPeers:
                if "|" in data:
                    peers = data.strip().split("|")
                    if len(peers[1]) > 0:
                        self.row["seeds"] = int(peers[0]) if peers[0].isnumeric() else -1
                        self.row["leech"] = int(peers[1]) if peers[1].isnumeric() else -1
                    else:
                        self.row["seeds"] = int(peers[0]) if peers[0].isnumeric() else -1
                        self.shouldGetLeechs = True
                else:
                    self.row["seeds"] = int(data) if data.isnumeric() else -1
                    self.row["leech"] = -1
                    self.shouldGetLeechs = True
                self.shouldGetPeers = False
                return

            if self.shouldGetSeeds:
                self.row["seeds"] = int(data) if data.isnumeric() else -1
                self.shouldGetSeeds = False

            if self.shouldGetLeechs and data != "|":
                self.row["leech"] = int(data) if data.isnumeric() else -1
                self.shouldGetLeechs = False

        def handle_endtag(self, tag):
            if self.insideCell and tag == self.TD:
                self.insideCell = False

            if self.insideRow and tag == self.TR:
                _qbt_prettyPrinter(self.row)
                self.column = 0
                self.row = self._new_row()
                self.insideRow = False
                self.shouldParseLink = True

            if self.insideResultTbody and tag == self.TBODY:
                self.insideResultTbody = False

    def download_torrent(self, info: str):
        print(download_file(info))

    def search(self, what: str, cat: str = "all"):
        parser = self.MyHtmlParser(self.url)
        what = what.replace("%20", "+")
        what = what.replace(" ", "+")
        page = 1

        page_url = f"{self.url}/browse.php?search={what}&page={page}"
        retrievedHtml = retrieve_url(page_url)
        pagination_matches = re.finditer(self.pagination_regex, retrievedHtml, re.MULTILINE)
        pagination_pages = [x.group() for x in pagination_matches]
        if len(pagination_pages) > 0:
            lastPage = int(
                pagination_pages[0]
                .replace('<div class="paginator_pages">', "")
                .replace("</div>", "")
                .split(" ")[3]
            )
        else:
            lastPage = 0
        page += 1

        if lastPage > 0:
            parser.feed(retrievedHtml)

            while page <= min(lastPage, MAX_PAGES):
                page_url = f"{self.url}/browse.php?search={what}&page={page}"
                retrievedHtml = retrieve_url(page_url)
                parser.feed(retrievedHtml)
                page += 1
        parser.close()
