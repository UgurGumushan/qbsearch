# VERSION: 1.3
"""
Nyaa.si anime search. Parses the HTML results table and follows pagination
(75 rows per page); each row links a magnet or its .torrent file depending on
the use_magent_links flag.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

# BEGIN GENERATED QBITT SAFETY PREAMBLE
# Slim stdlib-only helpers for standalone engines (rendered by `bun run gen`).
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import FIRST_COMPLETED as _qbt_FIRST_COMPLETED
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import wait as _qbt_wait
    from threading import Lock as _qbt_Lock
    from types import TracebackType as _QBTTracebackType
    from typing import TYPE_CHECKING
    from typing import Callable as _QBTCallable
    from typing import Protocol as _QBTProtocol
    from typing import TypeVar as _QBTTypeVar
    from typing import cast as _qbt_cast
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error

if TYPE_CHECKING:
    from typing_extensions import override
else:

    def override(function: _QBTCallable[..., object]) -> _QBTCallable[..., object]:
        return function


HTTP_TIMEOUT = 20.0
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.25
MAX_WORKERS = 4
SEARCH_DEADLINE = 60.0
MAX_PAGES = 30
MAX_DETAILS = 100
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

_qbt_socket.setdefaulttimeout(HTTP_TIMEOUT)
_QBT_RETRYABLE_HTTP_STATUS = frozenset((408, 425, 429, 500, 502, 503, 504))
_qbt_search_deadline: float | None = None
_QBTJobResult = _QBTTypeVar("_QBTJobResult")


class _QBTResponse(_QBTProtocol):
    status: int | None

    def close(self) -> None: ...

    def read(self, *args: object, **kwargs: object) -> bytes: ...

    def getcode(self) -> int: ...

    def geturl(self) -> str: ...

    def getheader(self, name: str, default: object = None) -> object: ...

    def info(self) -> _QBTResponse: ...

    def get(self, name: str, default: object = None) -> object: ...


class _QBTResponseContext(_QBTResponse, _QBTProtocol):
    def __enter__(self) -> _QBTResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool: ...


_qbt_urlopen_typed = _qbt_cast(_QBTCallable[..., _QBTResponseContext], _qbt_urlopen)


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


def _qbt_new_deadline() -> float:
    global _qbt_search_deadline
    _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


def _qbt_sleep(attempt: int, deadline: float | None = None) -> bool:
    if deadline is None:
        deadline = _qbt_get_deadline()
    remaining = deadline - _qbt_time.monotonic()
    if remaining <= 0:
        return False
    delay = min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0, remaining)
    if delay > 0:
        _qbt_time.sleep(delay)
    return _qbt_time.monotonic() < deadline


class _QBTEmptyResponse:
    """Empty response fallback so one dead request never aborts a search."""

    status: int | None = 200
    code: int = 200
    _url: str

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: _QBTTracebackType | None,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *_args: object, **_kwargs: object) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, _name: str, default: object = None) -> object:
        return default

    def info(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def get(self, _name: str, default: object = None) -> object:
        return default


def _qbt_empty_response(url: object) -> _QBTResponseContext:
    return _qbt_cast(_QBTResponseContext, _qbt_cast(object, _QBTEmptyResponse(url)))


def _qbt_response_limit(limit: object = None) -> int:
    value = MAX_RESPONSE_BYTES if limit is None else limit
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(MAX_RESPONSE_BYTES))


def _qbt_read_response(response: _QBTResponse, limit: object = None) -> bytes:
    """Read at most the configured response limit from an HTTP response."""
    return response.read(_qbt_response_limit(limit))


class _QBTBoundedResponse:
    """Response proxy that bounds the existing no-argument read() call sites."""

    def __init__(self, response: _QBTResponse) -> None:
        self._qbt_response = response

    def __enter__(self) -> "_QBTBoundedResponse":
        self._qbt_response = self._qbt_response.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool:
        return self._qbt_response.__exit__(exc_type, exc_value, traceback)

    def read(self, size: object = None, *_args: object, **_kwargs: object) -> bytes:
        if size is None:
            return _qbt_read_response(self._qbt_response)
        try:
            requested = int(size)
        except (TypeError, ValueError):
            return _qbt_read_response(self._qbt_response)
        if requested < 0:
            return _qbt_read_response(self._qbt_response)
        return _qbt_read_response(
            self._qbt_response,
            min(requested, _qbt_response_limit()),
        )

    def close(self) -> None:
        self._qbt_response.close()

    def __getattr__(self, name: str) -> object:
        return getattr(self._qbt_response, name)


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times; return empty on failure."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result: object = operation()
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
        if attempt + 1 < attempts and not _qbt_sleep(attempt):
            return ""
    return ""


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with timeout/retry policy; return an empty response when exhausted."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=timeout)
            else:
                response = _qbt_urlopen_typed(url, data=data, timeout=timeout, context=context)
            status: object = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return _qbt_cast(
                _QBTResponseContext,
                _qbt_cast(object, _QBTBoundedResponse(response)),
            )
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _qbt_empty_response(url)
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
            return _qbt_empty_response(url)
        if attempt + 1 < attempts and not _qbt_sleep(attempt):
            return _qbt_empty_response(url)
    return _qbt_empty_response(url)


_qbt_retrieve_url = _qbt_cast(_QBTCallable[..., object], _qbt_helper_retrieve_url)


def retrieve_url(*args: object, **kwargs: object) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result: object) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        printer = _qbt_cast(_QBTCallable[[object], None], prettyPrinter)
        printer(result)


def _qbt_run_parallel(
    worker: _QBTCallable[..., _QBTJobResult],
    jobs: _QBTIterable[object],
    deadline: float | None = None,
) -> list[_QBTJobResult]:
    """Run bounded worker jobs, preserving completed work after failures."""
    if deadline is None:
        deadline = _qbt_get_deadline()
    if deadline - _qbt_time.monotonic() <= 0:
        return []
    worker_limit = max(1, int(MAX_WORKERS))
    job_iterator = iter(jobs)
    initial_jobs: list[object] = []
    for _ in range(worker_limit):
        try:
            initial_jobs.append(next(job_iterator))
        except StopIteration:
            break
    if not initial_jobs or deadline - _qbt_time.monotonic() <= 0:
        return []
    executor = _QBTThreadPoolExecutor(max_workers=len(initial_jobs))
    pending: set[_QBTFuture[_QBTJobResult]] = set()
    results: list[_QBTJobResult] = []
    try:
        for job in initial_jobs:
            if deadline - _qbt_time.monotonic() <= 0:
                break
            if isinstance(job, tuple):
                pending.add(executor.submit(worker, *job))
            else:
                pending.add(executor.submit(worker, job))
        while pending:
            remaining = deadline - _qbt_time.monotonic()
            if remaining <= 0:
                break
            done, pending = _qbt_wait(
                pending,
                timeout=remaining,
                return_when=_qbt_FIRST_COMPLETED
            )
            if not done:
                break
            for future in done:
                try:
                    results.append(future.result())
                except Exception:
                    pass
                if deadline - _qbt_time.monotonic() <= 0:
                    continue
                try:
                    job = next(job_iterator)
                except StopIteration:
                    continue
                if isinstance(job, tuple):
                    pending.add(executor.submit(worker, *job))
                else:
                    pending.add(executor.submit(worker, job))
    finally:
        for future in pending:
            _ = future.cancel()
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            _ = executor.shutdown(wait=False)
    return results


__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_read_response",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


class nyaasi:
    """Class used by qBittorrent to search for torrents."""

    url: str = "https://nyaa.si"
    name: str = "Nyaa.si"

    # Whether to use magnet links or download torrent files ###################
    #
    # Set to 'True' to use magnet links, or 'False' to use torrent files
    use_magent_links: bool = True
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

        @override
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

        @override
        def handle_endtag(self, tag: str) -> None:
            """Handle the closing of table cells."""
            if tag == "td":
                self.start_td()

        def start_a(self, attrs: list[tuple[str, str | None]]) -> None:
            """Handle the opening of anchor tags."""
            params = self._attrs_to_dict(attrs)
            # get torrent name
            if "title" in params and "class" not in params and params.get("href", "").startswith(
                "/view/"
            ):
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

        @override
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
        _qbt_new_deadline()
        url = str(
            f"{self.url}/?f=0&s=seeders&o=desc&c={self.supported_categories.get(cat)}&q={what}"
        )

        page = 1
        page_size = 75
        seen_results: set[str] = set()
        emitted = 0
        for _ in range(MAX_PAGES):
            res = retrieve_url(url + f"&p={page}")
            hits: list[SearchResults] = []
            parser = self.NyaasiParser(hits, self.url, self.use_magent_links)
            parser.feed(res)
            parser.close()
            for each in hits:
                if emitted >= MAX_DETAILS:
                    break
                result_key = str(each.get("link", "")) or str(each.get("desc_link", ""))
                if not result_key or result_key in seen_results:
                    continue
                seen_results.add(result_key)
                _qbt_prettyPrinter(each)
                emitted += 1

            if emitted >= MAX_DETAILS or len(hits) < page_size:
                break
            page += 1
