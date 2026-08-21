# VERSION: 1.2
"""
Nyaa.pantsu anime search. Parses the HTML results table (name, size, seeds,
leeches) and follows pagination up to 300 results per page until the site
returns a short page.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
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
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
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


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

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


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
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
        if attempt + 1 < max(1, int(MAX_ATTEMPTS)):
            _qbt_sleep(attempt)
    return ""


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen_typed(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return response
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
            # A malformed request is not useful to retry, but it must not
            # abort the qBittorrent search process.
            return _qbt_empty_response(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
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
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures: list[_QBTFuture[_QBTJobResult]] = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results: list[_QBTJobResult] = []
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
            _ = future.cancel()
    finally:
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            _ = executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# These hooks are available to standalone engines even when a particular
# engine does not call every optional adapter directly.
__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


class nyaapantsu:
    """Class used by qBittorrent to search for torrents"""

    url: str = "https://nyaa.pantsu.cat"
    name: str = "Nyaa.pantsu"
    # defines which search categories are supported by this search engine
    # and their corresponding id. Possible categories are:
    # 'all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures',
    # 'books'
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "_",
        "anime": "3_",
        "books": "4_",
        "music": "2_",
        "pictures": "6_",
        "software": "1_",
        "tv": "5_",
        "movies": "5_",
    }

    class NyaaPantsuParser(HTMLParser):
        """Parses Nyaa.pantsu browse page for search resand prints them"""

        class DataType(Enum):
            """Enumeration to keep track of the TD Type to use in handle_data()'"""

            NONE = 0
            NAME = 1
            SEEDS = 2
            LEECH = 3
            SIZE = 4
            DATE = 5

        def __init__(
            self,
            res: list[SearchResults],
            url: str = "https://nyaa.pantsu.cat",
        ):
            try:
                super().__init__()
            except Exception:  #  See: http://stackoverflow.com/questions/9698614/
                HTMLParser.__init__(self)

            self.engine_url: str = url
            self.results: list[SearchResults] = res
            self.curr: dict[str, str | int] | None = None
            self.td_type: object = self.DataType.NONE

        @staticmethod
        def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            return {key: (value if value is not None else "") for key, value in attrs}

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            """Calls element specific functions based on tag."""
            if tag == "a":
                self.start_a(attrs)
            if tag == "tr":
                self.start_tr(attrs)
            if tag == "td":
                self.start_td(attrs)

        def start_tr(self, attr: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attr)
            if "class" in params and params["class"].startswith("torrent-info"):
                self.curr = {"engine_url": self.engine_url}

        def start_a(self, attr: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attr)
            # get torrent name
            if "href" in params and params["href"].startswith("/view/"):
                if self.curr:
                    self.curr["desc_link"] = self.engine_url + params["href"]
                # also get name from handle_data()
                self.td_type = self.DataType.NAME
            # get torrent magnet link
            elif "href" in params and params["href"].startswith("magnet:?"):
                if self.curr:
                    self.curr["link"] = params["href"]

        def start_td(self, attr: list[tuple[str, str | None]]) -> None:
            """Parses TD elements and sets self.td_type based on its html class.

            If last TD element for the current hit is reached it appends it to
            results and cleans up.
            """
            params = self._attrs_to_dict(attr)

            # get seeds from handle_data()
            if "class" in params and params["class"].startswith("tr-se"):
                self.td_type = self.DataType.SEEDS
            # get leechers from handle_data()
            elif "class" in params and params["class"].startswith("tr-le"):
                self.td_type = self.DataType.LEECH
            # get size from handle_data()
            elif "class" in params and params["class"].startswith("tr-size"):
                self.td_type = self.DataType.SIZE
            # get publication date from handle_data()
            elif "class" in params and params["class"].startswith("tr-date"):
                self.td_type = self.DataType.DATE
            # default: current innerContent does not concern us: pass.
            else:
                self.td_type = self.DataType.NONE

        @override
        def handle_endtag(self, tag: str) -> None:
            """Save a result after its date cell has been consumed."""
            if tag != "tr" or self.curr is None:
                return
            result = SearchResults(
                link=str(self.curr.get("link", "")),
                name=str(self.curr.get("name", "")),
                size=str(self.curr.get("size", "")),
                seeds=int(self.curr.get("seeds", -1)),
                leech=int(self.curr.get("leech", -1)),
                engine_url=str(self.curr.get("engine_url", "")),
                desc_link=str(self.curr.get("desc_link", "")),
            )
            if "pub_date" in self.curr:
                result["pub_date"] = int(self.curr["pub_date"])
            self.results.append(result)
            self.td_type = self.DataType.NONE
            self.curr = None

        @override
        def handle_data(self, data: str) -> None:
            """Strip textContent data for search result based on td type"""
            if self.curr is None:
                return
            # Get result name
            if self.td_type == self.DataType.NAME:
                name = str(self.curr.get("name", ""))
                name += data.strip()
                self.curr["name"] = name
                self.td_type = self.DataType.NONE
            # Get no. of seeds
            elif self.td_type == self.DataType.SEEDS:
                try:
                    self.curr["seeds"] = int(data.strip())
                except Exception:
                    self.curr["seeds"] = -1
                finally:
                    self.td_type = self.DataType.NONE
            # Get no. of leechers
            elif self.td_type == self.DataType.LEECH:
                try:
                    self.curr["leech"] = int(data.strip())
                except Exception:
                    self.curr["leech"] = -1
                finally:
                    self.td_type = self.DataType.NONE
            # Get size
            elif self.td_type == self.DataType.SIZE:
                self.curr["size"] = data.strip()
                self.td_type = self.DataType.NONE
            # Get the publication date.  The site stores this as an absolute
            # UTC-looking timestamp; leave relative/unknown labels alone.
            elif self.td_type == self.DataType.DATE:
                match = re.search(
                    r"\d{4}[-/]\d{2}[-/]\d{2} \d{2}:\d{2}(?::\d{2})?",
                    data,
                )
                if match:
                    date_text = match.group()
                    for date_format in (
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d %H:%M",
                        "%Y/%m/%d %H:%M:%S",
                        "%Y/%m/%d %H:%M",
                    ):
                        try:
                            self.curr["pub_date"] = int(
                                datetime.strptime(date_text, date_format)
                                .replace(tzinfo=timezone.utc)
                                .timestamp()
                            )
                            break
                        except ValueError:
                            pass
                self.td_type = self.DataType.NONE
            # Default: self.td_type is unset, current textConent is not
            # interesting, do nothing.
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

        page = 1
        hits: list[SearchResults] = []
        parser = self.NyaaPantsuParser(hits, self.url)
        for _ in range(MAX_PAGES):
            url = str(
                f"{self.url}/search/{page}?s=0&sort=5&order=false&max=300&c="
                + f"{self.supported_categories.get(cat)}&q={what}"
            )
            # pantsu is very volatile.
            try:
                res = retrieve_url(url)
                parser.feed(res)
            except Exception:
                pass

            for each in hits:
                _qbt_prettyPrinter(each)

            if len(hits) < 300:
                break
            del hits[:]
            page += 1

        parser.close()
