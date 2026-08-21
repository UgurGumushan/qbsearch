# VERSION: 1.2
"""
UnionDHT (http://uniondht.org) search engine. DHT tracker front-end: scrapes
the tracker page in batches of 50 and emits parsed rows after each bounded
search.  Output is serialized by the generated safety preamble.
"""

from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

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


TorrentInfo = dict[str, str]


class uniondht:
    name = 'UnionDHT'
    url = 'http://uniondht.org'
    supported_categories: ClassVar[dict[str, str]]  = {'all': ''}

    class UnionDHTParser(HTMLParser):
        def __init__(self, url):
            super().__init__()
            self.engine_url = url
            self.torrent_info = self.default_torrent_info()
            self.results: list[TorrentInfo] = []
            self.total_results = 0
            self.find_total_results = True
            self.find_torrent = False
            self.find_desc_link = False
            self.find_name = False
            self.find_link = False
            self.find_seeds = False
            self.find_leech_class = False
            self.find_leech = False
            self.parse_total_results = False
            self.parse_name = False
            self.parse_size = False
            self.parse_seeds = False
            self.parse_leech = False
            self.print_result = False

        def default_torrent_info(self) -> TorrentInfo:
            return {'link': '', 'name': '', 'size': '-1', 'seeds': '-1', 'leech': '-1', 'engine_url': self.engine_url, 'desc_link': ''}

        def handle_starttag(self, tag, attrs):
            if self.find_total_results:
                if tag == 'p':
                    attributes = dict(attrs)
                    if 'class' in attributes and attributes['class'] == 'floatR':
                        self.find_total_results = False
                        self.parse_total_results = True
            elif self.find_torrent:
                if tag == 'tr':
                    attributes = dict(attrs)
                    if 'id' in attributes and (attributes['id'] or '').startswith('tor'):
                        self.find_torrent = False
                        self.find_desc_link = True
            elif self.find_desc_link:
                if tag == 'a':
                    attributes = dict(attrs)
                    if 'href' in attributes and (attributes['href'] or '').startswith('/topic'):
                        self.torrent_info['desc_link'] = self.engine_url + attributes['href']
                        self.find_desc_link = False
                        self.find_name = True
            elif self.find_name:
                if tag == 'b':
                    self.find_name = False
                    self.parse_name = True
            elif self.find_link:
                if tag == 'wbr':
                    self.find_link = False
                    self.parse_name = True
                elif tag == 'a':
                    attributes = dict(attrs)
                    if 'href' in attributes and (attributes['href'] or '').startswith('/dl.'):
                        self.torrent_info['link'] = self.engine_url + attributes['href']
                        self.find_link = False
                        self.parse_size = True
            elif self.find_seeds:
                if tag == 'td':
                    attributes = dict(attrs)
                    if 'class' in attributes and (attributes['class'] or '').find('seed') != -1:
                        self.find_seeds = False
                        self.parse_seeds = True
            elif self.find_leech_class:
                if tag == 'td':
                    attributes = dict(attrs)
                    if 'class' in attributes and (attributes['class'] or '').find('leech') != -1:
                        self.find_leech_class = False
                        self.find_leech = True
            elif self.find_leech and tag == 'b':
                self.find_leech = False
                self.parse_leech = True

        def handle_data(self, data):
            if self.parse_total_results:
                total_results = data.split(':')[1].split('(')[0].strip()
                self.total_results = int(total_results)
                self.parse_total_results = False
                self.find_torrent = True
            elif self.parse_name:
                self.torrent_info['name'] += data.strip()
                self.parse_name = False
                self.find_link = True
            elif self.parse_size:
                self.torrent_info['size'] = data.replace('\xa0', '').strip()
                self.parse_size = False
                self.find_seeds = True
            elif self.parse_seeds:
                self.torrent_info['seeds'] = data.strip()
                self.parse_seeds = False
                self.find_leech_class = True
            elif self.parse_leech:
                self.torrent_info['leech'] = data.strip()
                self.parse_leech = False
                self.print_result = True

        def handle_endtag(self, tag):
            if self.print_result:
                self.results.append(self.torrent_info.copy())
                self.torrent_info = self.default_torrent_info()
                self.print_result = False
                self.find_torrent = True

    def search(self, what, cat='all'):
        parser = self.UnionDHTParser(self.url)
        for page_number in range(1, MAX_PAGES + 1):
            torrent_count = (page_number - 1) * 50
            search_url = f'{self.url}/tracker.php?nm={what}&start={torrent_count}'
            try:
                retrieved_page = retrieve_url(search_url)
                if not retrieved_page:
                    break
                before = len(parser.results)
                parser.feed(retrieved_page)
            except Exception:
                break
            if len(parser.results) == before:
                break
            if parser.total_results and torrent_count + 50 >= parser.total_results:
                break
        parser.close()
        for result in parser.results:
            _qbt_prettyPrinter(result)


if __name__ == '__main__':
    engine = uniondht()
    engine.search('ubuntu')
