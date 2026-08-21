# VERSION: 1.2
"""
MikanProject (mikanime.tv) anime search. Parses the HTML search results page;
each row links its detail page and its .torrent file.
"""
from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from typing import ClassVar, TypedDict, cast

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


try:
    import requests
except ModuleNotFoundError:
    requests = None

class MikananiRow(TypedDict, total=False):
    link: str
    name: str
    size: str
    seeds: int
    leech: int
    engine_url: str
    desc_link: str
    pub_date: int


class mikanani:
    """Class used by qBittorrent to search for torrents."""

    url = 'https://mikanime.tv'
    name = 'mikanani'

    ###########################################################################

    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories: ClassVar[dict[str, str]]  = {'all': ''}

    class mikananiParser(HTMLParser):
        """Parses a mikanime.tv search page for results and stores them."""

        def __init__(self, res: list[SearchResults], url: str) -> None:
            """Construct a mikanime.tv HTML parser.

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
            self.results: list[SearchResults] = res
            self.curr: MikananiRow | None = None
            self.td_counter = -1
            self.span_counter = 0
            self.find_title = False

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            """Tell the parser what to do with which tags."""
            if tag == 'a':
                self.start_a(attrs)

        def handle_endtag(self, tag: str) -> None:
            """Handle the closing of table cells."""
            if tag == 'td':
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle the opening of anchor tags."""
            params = {key: value for key, value in attrs if value is not None}
            css_class = params.get('class')
            href = params.get('href')
            # get torrent name
            if (
                css_class is not None
                and css_class.startswith('magnet')
                and 'target' in params
                and href is not None
            ):
                self.find_title = True
                hit: MikananiRow = {'desc_link': self.engine_url + href}
                self.td_counter += 1
                if self.curr is None:
                    hit['engine_url'] = self.engine_url
                    hit['seeds'] = -1
                    hit['leech'] = -1
                    self.curr = hit
            elif href is not None and self.curr is not None:
                # skip unrelated links
                if not href.endswith(".torrent"):
                    return

                # check whether to use torrent files or magnet links,
                # then search for a matching download link, and move on
                if href.endswith(".torrent"):
                    self.curr['link'] = self.engine_url + href
            else:
                pass

        def start_td(self) -> None:
            """Handle the opening of a table cell tag."""
            # Keep track of timers
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 4:
                if self.curr is not None:
                    self.results.append(cast(SearchResults, cast(object, self.curr)))
                self.curr = None
                self.td_counter = -1
                self.find_title = False
                self.span_counter = -1

        def handle_data(self, data: str) -> None:
            """Extract data about the torrent."""
            if self.curr is None:
                return
            # These fields matter
            if self.td_counter > -1\
                    and self.td_counter <= 4:
                # Catch the name
                if self.find_title and self.td_counter == 0:
                    self.curr['name'] = data.strip()
                    self.find_title = False
                # Catch the size
                elif self.td_counter == 1:
                    self.curr['size'] = data.strip()
                # Catch the publication date
                elif self.td_counter == 2:
                    try:
                        self.curr['pub_date'] = int(
                            datetime.strptime(data.strip(), '%Y/%m/%d %H:%M').timestamp()
                        )
                    except ValueError:
                        pass
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py

    def search(self, what: str, cat: str = 'all') -> None:
        """
        Retreive and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                     (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """
        url = self.url

        # print(url)
        hits: list[SearchResults] = []
        page = 1
        parser = self.mikananiParser(hits, self.url)
        for _ in range(1):
            requirement = f'{url}/Home/Search?page={page}&searchstr={what}&subgroupid={cat}'
            # s = requests.Session()
            # res = new_retrieve_url(requirement,s)
            res = retrieve_url(requirement)
            # print(res)
            parser.feed(res)
            # print(hits)
            for each in hits:
                _qbt_prettyPrinter(each)

            # if len(hits) < 30:
            #     break
            # del hits[:]
            # page += 1
            break

        parser.close()


def new_retrieve_url(url: str, s: object) -> str:
    """ Return the content of the url page as a string """
    if requests is None:
        return ""
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    headers = {'User-Agent': user_agent}
    session = requests.Session()
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        try:
            response = session.get(url, headers=headers, timeout=HTTP_TIMEOUT)
            if response.status_code >= 400:
                return ""
            return response.text
        except Exception:
            if attempt + 1 < max(1, int(MAX_ATTEMPTS)):
                _qbt_sleep(attempt)
    return ""
