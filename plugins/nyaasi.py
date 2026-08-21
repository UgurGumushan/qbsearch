# VERSION: 1.3
"""
Nyaa.si anime search. Parses the HTML results table and follows pagination
(75 rows per page); each row links a magnet or its .torrent file depending on
the use_magent_links flag.
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


class nyaasi:
    """Class used by qBittorrent to search for torrents."""

    url = "https://nyaa.si"
    name = "Nyaa.si"

    # Whether to use magnet links or download torrent files ###################
    #
    # Set to 'True' to use magnet links, or 'False' to use torrent files
    use_magent_links = True
    #
    ###########################################################################

    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0_0",
        "anime": "1_0",
        "books": "3_0",
        "music": "2_0",
        "pictures": "5_0",
        "software": "6_0",
        "tv": "4_0",
        "movies": "4_0",
    }

    class NyaasiParser(HTMLParser):
        """Parses Nyaa.si browse page for search results and stores them."""

        def __init__(self, res: list[SearchResults], url: str, use_magnet: bool = True):
            """Construct a nyaasi html parser.

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

            self.engine_url: str = url
            self.use_magnet_links: bool = use_magnet
            self.results: list[SearchResults] = res
            self.curr: SearchResults | None = None
            self.td_counter: int = -1

        @staticmethod
        def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            return {key: (value if value is not None else "") for key, value in attrs}

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            """Tell the parser what to do with which tags."""
            if tag == "a":
                self.start_a(attrs)
            elif tag == "td" and self.td_counter == 2 and self.curr is not None:
                ts = self._attrs_to_dict(attrs).get("data-timestamp")
                try:
                    self.curr["pub_date"] = int(ts) if ts is not None else -1
                except ValueError:
                    self.curr["pub_date"] = -1

        def handle_endtag(self, tag: str) -> None:
            """Handle the closing of table cells."""
            if tag == "td":
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle the opening of anchor tags."""
            params = self._attrs_to_dict(attrs)
            # get torrent name
            if "title" in params and "class" not in params and params["href"].startswith("/view/"):
                hit: SearchResults = {
                    "link": "",
                    "name": params["title"],
                    "size": "",
                    "seeds": -1,
                    "leech": -1,
                    "engine_url": self.engine_url,
                    "desc_link": self.engine_url + params["href"],
                }
                if not self.curr:
                    self.curr = hit
            elif "href" in params and self.curr:
                # skip unrelated links
                if not params["href"].startswith("magnet:?") and not params["href"].endswith(
                    ".torrent"
                ):
                    return

                # check whether to use torrent files or magnet links,
                # then search for a matching download link, and move on
                if not self.use_magnet_links and params["href"].endswith(".torrent"):
                    self.curr["link"] = self.engine_url + params["href"]
                    self.td_counter += 1

                elif params["href"].startswith("magnet:?") and self.use_magnet_links:
                    self.curr["link"] = params["href"]
                    self.td_counter += 1

        def start_td(self) -> None:
            """Handle the opening of a table cell tag."""
            # Keep track of timers
            if self.td_counter >= 0:
                self.td_counter += 1

            # Add the hit to the results,
            # then reset the counters for the next result
            if self.td_counter >= 5 and self.curr is not None:
                self.results.append(self.curr)
                self.curr = None
                self.td_counter = -1

        def handle_data(self, data: str) -> None:
            if self.curr is None:
                return
            """Extract data about the torrent."""
            # These fields matter
            if self.td_counter > 0 and self.td_counter <= 5:
                # Catch the size
                if self.td_counter == 1:
                    self.curr["size"] = data.strip()
                # Catch the seeds
                elif self.td_counter == 3:
                    try:
                        self.curr["seeds"] = int(data.strip())
                    except ValueError:
                        self.curr["seeds"] = -1
                # Catch the leechers
                elif self.td_counter == 4:
                    try:
                        self.curr["leech"] = int(data.strip())
                    except ValueError:
                        self.curr["leech"] = -1
                # The rest is not supported by prettyPrinter
                else:
                    pass

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = "all") -> None:
        """
        Retreive and parse engine search results by category and query.

        Parameters:
        :param what: a string with the search tokens, already escaped
                      (e.g. "Ubuntu+Linux")
        :param cat:  the name of a search category, see supported_categories.
        """
        url = str(
            f"{self.url}/?f=0&s=seeders&o=desc&c={self.supported_categories.get(cat)}&q={what}"
        )

        hits: list[SearchResults] = []
        page = 1
        parser = self.NyaasiParser(hits, self.url, self.use_magent_links)
        for _ in range(MAX_PAGES):
            res = retrieve_url(url + f"&p={page}")
            parser.feed(res)
            for each in hits:
                _qbt_prettyPrinter(each)

            if len(hits) < 75:
                break
            del hits[:]
            page += 1

        parser.close()
