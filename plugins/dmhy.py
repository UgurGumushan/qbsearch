# VERSION: 1.00
"""DMHY engine: Chinese anime, donghua, games and music torrents.

Rows are read from the topic-list table, and the .torrent link is
rebuilt from the row date and the magnet's info hash.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar, cast

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


class dmhy:
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their corresponding id,
    possible categories are ('all', 'anime', 'books', 'games', 'movies', 'pictures', 'software', 'tv').
    """

    url = 'https://share.dmhy.org'
    name = 'DMHY'
    supported_categories: ClassVar[dict[str, str]]  = {
        'all': '0'
    }

    class RowParser(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.rows: list[list[str]] = []
            self.in_topic_list = False
            self.depth = 0
            self.cur: dict[str, list[str]] | None = None

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            params = dict(attrs)
            if tag == 'table' and params.get('id') == 'topic_list':
                self.in_topic_list = True
                return
            if not self.in_topic_list:
                return
            if tag == 'tr':
                self.cur = {'raw': [], 'cells': []}
            elif tag == 'td' and self.cur is not None:
                self.cur['cells'].append('')

        def handle_data(self, data: str) -> None:
            if self.cur is not None and self.cur['cells']:
                self.cur['cells'][-1] += data

        def handle_endtag(self, tag: str) -> None:
            if not self.in_topic_list:
                return
            if tag == 'tr' and self.cur is not None:
                self.rows.append(self.cur['cells'])
                self.cur = None
            elif tag == 'table':
                self.in_topic_list = False

    @classmethod
    def analyze_torrent(cls, cells: list[list[str]]) -> list[SearchResults]:
        res: list[SearchResults] = []
        for cell in cells:
            if len(cell) < 7:
                continue
            date = re.sub(r'\s+', ' ', cell[0]).strip().split()[0]
            name = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[2])).strip()
            links = re.findall(r'href="([^"]*)"', cell[3])
            magnet = next((l for l in links if l.startswith('magnet:?')), '')
            desc_m = re.search(r'href="([^"]*)"', cell[2])
            desc_link = f"{cls.url}{desc_m.group(1)}" if desc_m else cls.url
            size = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[4])).strip()
            seeds = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[5])).strip()
            leech = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', cell[6])).strip()
            btih_m = re.search(r'btih:([0-9A-Fa-f]+)', magnet)
            link = f"https://dl.dmhy.org/{date}/{btih_m.group(1)}.torrent" if btih_m else magnet
            tmp: dict[str, str | int] = {
                'date': date,
                'name': name,
                'desc_link': desc_link,
                'engine_url': cls.url,
                'size': size,
                'seeds': int(seeds) if seeds.isdigit() else -1,
                'leech': int(leech) if leech.isdigit() else -1,
                'link': link,
            }
            # Keep the date field in the returned scraper record; qBittorrent's
            # printer contract only describes the common result fields.
            result = cast(SearchResults, cast(object, tmp))
            res.append(result)
            _qbt_prettyPrinter(result)
        return res

    def download_torrent(self, info: str) -> None:
        """
        Providing this function is optional.
        It can however be interesting to provide your own torrent download
        implementation in case the search engine in question does not allow
        traditional downloads (for example, cookie-based download).
        """
        print(download_file(info))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = 'all') -> None:
        """
        Here you can do what you want to get the result from the search engine website.
        Everytime you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `what` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `cat` is the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """
        hits: list[SearchResults] = []
        url = self.url
        page = 1

        for _ in range(MAX_PAGES):
            res = retrieve_url(f"{url}/topics/list/page/{page}?keyword={what.replace(' ', '+')}")
            parser = self.RowParser()
            parser.feed(res)
            parser.close()
            cells = parser.rows
            hits.extend(self.analyze_torrent(cells))
            page += 1
            if len(cells) < 80:
                break


if __name__ == '__main__':
    d = dmhy()
    d.search('C3魔方少女')
    print(1)
