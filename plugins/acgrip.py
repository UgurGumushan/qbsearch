# VERSION: 1.0
"""acg.rip engine: anime, manga, games and software search results.

Links are torrent-file downloads; result pages are followed one page at a
time until a short page is returned.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar

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


class acgrip:
    """qBittorrent search engine for acg.rip."""

    url = 'https://acg.rip'
    name = 'acg.rip'

    ###########################################################################

    # Map the qBittorrent search categories to the engine's own ids.
    # Possible categories: 'all', 'movies', 'tv', 'music', 'games', 'anime',
    # 'software', 'pictures', 'books'.
    supported_categories: ClassVar[dict[str, str]]  = {'all': '0_0'}

    class acgripParser(HTMLParser):
        """Parse an acg.rip results page and store the parsed hits."""

        def __init__(self, res: list[SearchResults], url: str) -> None:
            """Construct a acgrip html parser.

            Parameters:
            :param list res: a list to store the results in
            :param str url: the base url of the search engine
            :param str use_magnet: whether to link to magnet links or torrent
                                   files
            """
            try:
                super().__init__()
            except TypeError:
                #  See: http://stackoverflow.com/questions/9698614/
                HTMLParser.__init__(self)

            self.engine_url = url
            self.results = res
            self.curr: SearchResults | None = None
            self.td_counter = -1
            self.find_title = False
            self.span_counter = -1

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            """Dispatch opening tags to the matching helper."""
            if tag == 'a':
                self.start_a(attrs)
            if tag == 'span':
                self.start_span(attrs)

        def handle_endtag(self, tag: str) -> None:
            """Handle closing table-cell tags."""
            if tag == 'td':
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle opening anchor tags."""
            params = dict(attrs)
            href = params.get('href') or ''
            # Topic link: starts a new result row.
            if 'class' not in params and not href.endswith(".torrent")\
                    and href.startswith('/t/'):
                hit: SearchResults = {
                    'link': '',
                    'name': '',
                    'size': '',
                    'seeds': -1,
                    'leech': -1,
                    'engine_url': self.engine_url,
                    'desc_link': self.engine_url + href,
                }
                self.td_counter += 1
                if not self.curr:
                    self.curr = hit
            elif 'href' in params and self.curr:
                # skip unrelated links
                if not href.endswith(".torrent"):
                    return

                # check whether to use torrent files or magnet links,
                # then search for a matching download link, and move on
                if href.endswith(".torrent"):
                    self.curr['link'] = self.engine_url + href

        def start_span(self, attrs: list[tuple[str, str | None]]) -> None:
            """Track which of the seeds/leech spans in a row's stats cell."""
            params = dict(attrs)
            class_name = params.get('class') or ''
            if class_name == 'title':
                self.find_title = True
            elif class_name and not class_name.startswith('label'):
                if self.span_counter == -1:
                    self.span_counter += 1
                elif self.span_counter == 2:
                    self.span_counter -= 1
            else:
                pass

        def start_td(self) -> None:
            """Handle the opening of a table cell tag."""
            # Count the row's cells until the row is complete.
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 4:
                if self.curr is not None:
                    self.results.append(self.curr)
                self.curr = None
                self.td_counter = -1
                self.find_title = False
                self.span_counter = -1

        def handle_data(self, data: str) -> None:
            """Extract data about the torrent."""
            if self.curr is None:
                return
            if self.td_counter > -1\
                    and self.td_counter <= 4:
                # Row 0 carries the torrent name.
                if self.find_title and self.td_counter == 0:
                    self.curr['name'] = data.strip()
                    self.find_title = False
                # Catch the size
                elif self.td_counter == 2:
                    self.curr['size'] = data.strip()
                elif self.td_counter == 3:
                    # Catch the seeds
                    if self.span_counter == 0:
                        try:
                            self.span_counter += 2
                            self.curr['seeds'] = int(data.strip())
                        except ValueError:
                            self.curr['seeds'] = -1
                    # Catch the leech
                    elif self.span_counter == 1:
                        try:
                            self.span_counter += 2
                            self.curr['leech'] = int(data.strip())
                        except ValueError:
                            self.curr['leech'] = -1
                    else:
                        pass
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py

    def search(self, what: str, cat: str = 'all') -> None:
        """
        Retrieve and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                     (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """
        url = self.url

        hits: list[SearchResults] = []
        page = 1
        parser = self.acgripParser(hits, self.url)
        for _ in range(MAX_PAGES):
            res = retrieve_url(f'{url}/page/{page}?term={what}')
            parser.feed(res)
            for each in hits:
                _qbt_prettyPrinter(each)

            if len(hits) < 30:
                break
            del hits[:]
            page += 1

        parser.close()
