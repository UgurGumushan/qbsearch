# VERSION: 1.0
"""CalidadTorrent engine: Spanish movies, series and anime torrents.

Each torrent card is followed to grab its .torrent link, and all result
pages are parsed until the site reports no more matches.
"""
from __future__ import annotations

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


class calidadtorrent:
    url = 'https://calidadtorrent.com'
    headers: ClassVar[dict[str, str]] = {
        'Referer': url
    }
    name = 'CalidadTorrent'
    supported_categories: ClassVar[dict[str, str]] = {
        'all': 'all'
    }

    no_results_regex = r'<p.*?>No se ha encontrado ning[uú]n resultado.</p>'

    class SearchResultsParser(HTMLParser):
        def error(self, message: str) -> None:
            pass

        DIV, A = ('div', 'a')

        expected_x_data = "{ showDetail: true }"
        torrent_link_regex = r'\/torrents\/.+?\.torrent'
        title_regex = r'<h1.*?>.*?</h1>'

        count = 0

        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.headers = {
                'Referer': url
            }

            self.insideResultList = False
            self.insideResultContainer = False
            self.insideResult = False
            self.insideLink = False

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            params = dict(attrs)
            css_classes = params.get('class') or ''
            x_data = params.get('x-data')

            if tag == self.DIV and 'result-list' in css_classes:
                self.insideResultList = True
                return

            if self.insideResultList and tag == self.DIV and x_data == self.expected_x_data:
                self.insideResultContainer = True
                return

            if self.insideResultContainer and tag == self.DIV and 'relative' in css_classes:
                self.insideResult = True
                return

            if self.insideResult and tag == self.A:
                self.count += 1
                self.insideLink = True
                href = params.get('href')
                if href is None:
                    return
                retrieved_html = retrieve_url(href, self.headers)

                link_matches = re.finditer(self.torrent_link_regex, retrieved_html, re.MULTILINE)
                title_matches = re.finditer(self.title_regex, retrieved_html, re.MULTILINE)

                torrent_link = [x.group() for x in link_matches]
                title = [x.group() for x in title_matches]

                row: SearchResults = {
                    'link': f'{calidadtorrent.url}{torrent_link[0]}',
                    'name': re.sub(r'</h1>', '',re.sub(r'<h1.+?>', '', title[0])),
                    'size': 0,
                    'seeds': -1,
                    'leech': -1,
                    'engine_url': calidadtorrent.url,
                    'desc_link': href
                }
                _qbt_prettyPrinter(row)
                return

        def handle_endtag(self, tag: str) -> None:
            if self.insideLink and tag == self.A:
                self.insideLink = False
                return

            if not self.insideLink and self.insideResult and tag == self.DIV:
                self.insideResult = False
                return

            if not self.insideResult and self.insideResultContainer and tag == self.DIV:
                self.insideResultContainer = False
                return

            if not self.insideResultContainer and self.insideResultList and tag == self.DIV:
                self.insideResultList = False
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def get_search_url(self, what: str, page: int) -> str:
        return f'{self.url}/buscar/page/{page}?q={what}'

    def has_results(self, html: str) -> bool:
        no_results_matches = re.finditer(self.no_results_regex, html, re.MULTILINE)
        no_results = [x.group() for x in no_results_matches]
        return len(no_results) == 0

    def search(self, what: str, cat: str) -> None:
        what = what.replace('%20', '+')
        page = 1

        for _ in range(MAX_PAGES):
            retrieved_html = retrieve_url(self.get_search_url(what,page), self.headers)
            if not retrieved_html:
                break

            if self.has_results(retrieved_html):
                parser = self.SearchResultsParser(self.url)
                parser.feed(retrieved_html)
                parser.close()

                page += 1
            else:
                break
