# VERSION: 0.02
"""AniDex engine: anime, games, music and other niche category search.

All additional result pages are fetched concurrently in threads (offset
pagination) and results are magnet links.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar

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


class anidex:
    url = 'https://anidex.info/'
    name = 'AniDex'
    supported_categories: ClassVar[dict[str, str]]  = {
        'all': '',
        'music': 'id=9,10,11&',
        'games': 'id=12&',
        'anime': 'id=1,2,3&',
        'software': 'id=13&',
        'pictures': 'id=14&',
        'books': 'id=6,7,8&',
    }

    class anidexParser(HTMLParser):
        url = 'https://anidex.info'
        TR, TH, TD, A, SPAN = 'tr', 'th', 'td', 'a', 'span'
        inRow = False
        getSize = False
        getSeed = False
        getLeech = False
        def __init__(self) -> None:
            super().__init__()
            self.this_result: SearchResults = {
                'link': '',
                'name': '',
                'size': '',
                'seeds': -1,
                'leech': -1,
                'engine_url': self.url,
            }

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag == self.TR and self.inRow is False:
                self.inRow = True
            if tag == self.TH and self.inRow is True:
                self.inRow = False
            if self.inRow is True and tag == self.TD:
                my_attrs = dict(attrs)
                if my_attrs.get('class') == 'text-center td-992' and my_attrs.get('title') is None:
                    self.getSize = True
                if my_attrs.get('class') == 'text-success text-right':
                    self.getSeed = True
                if my_attrs.get('class') == 'text-danger text-right':
                    self.getLeech = True
            if self.inRow and tag == self.A:
                my_attrs = dict(attrs)
                href = my_attrs.get('href')
                if href is not None and href.startswith('magnet'):
                    self.this_result['link'] = href
                if my_attrs.get('class') == 'torrent':
                    self.this_result['desc_link'] = self.url + (href or '')
            if self.inRow and tag == self.SPAN:
                my_attrs = dict(attrs)
                title = my_attrs.get('title')
                if my_attrs.get('class') == 'span-1440' and title is not None:
                    self.this_result['name'] = title

        def handle_endtag(self, tag: str) -> None:
            if self.inRow is True and tag == self.TR:
                self.inRow = False
                self.this_result['engine_url'] = self.url
                _qbt_prettyPrinter(self.this_result)

        def handle_data(self, data: str) -> None:
            if self.inRow and self.getSize:
                self.this_result['size'] = data.strip().replace(',', '')
                self.getSize = False
            if self.inRow and self.getSeed:
                seed_value = data.strip().replace(',', '')
                self.this_result['seeds'] = int(seed_value) if seed_value.isdigit() else -1
                self.getSeed = False
            if self.inRow and self.getLeech:
                leech_value = data.strip().replace(',', '')
                self.this_result['leech'] = int(leech_value) if leech_value.isdigit() else -1
                self.getLeech = False

    def do_search(self, url: str) -> None:
        webpage = retrieve_url(url)
        adexParser = self.anidexParser()
        adexParser.feed(webpage)

    def search(self, what: str, cat: str = 'all') -> None:
        query = str(what).replace(' ', '+')
        search_url = self.url + \
            '?s=seeders&o=desc&' + \
            self.supported_categories[cat.lower()] + \
            'q=' + query

        webpage = retrieve_url(search_url)
        total_matches = re.findall(r'Showing[^f]+f(.+?)torrents', webpage)
        if not total_matches:
            return
        try:
            total_results = int(total_matches[0].strip().replace(',', ''))
        except ValueError:
            return

        adexParser = self.anidexParser()
        adexParser.feed(webpage)

        offsets = range(50, min(total_results, (MAX_PAGES + 1) * 50), 50)
        jobs = [(search_url + '&offset=' + str(offset),) for offset in offsets]
        _qbt_run_parallel(self.do_search, jobs, _qbt_new_deadline())


if __name__ == '__main__':
    a = anidex()
    a.search('DS', 'all')
