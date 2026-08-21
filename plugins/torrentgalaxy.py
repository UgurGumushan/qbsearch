# VERSION: 0.08
"""
TorrentGalaxy (https://torrentgalaxy.to) search engine. Scrapes rows of
tgxtablerow/tgxtablecell divs, using cell class and text alignment to decide
which field (name, size, seeds, leeches, pub date) the text belongs to.
"""

from __future__ import annotations

import math
import re
import time
from html.parser import HTMLParser
from typing import ClassVar, cast

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


class torrentgalaxy:
    url: str = "https://torrentgalaxy.to"
    name: str = "TorrentGalaxy"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "",
        "movies": "c3=1&c46=1&c45=1&c42=1&c4=1&c1=1&",
        "tv": "c41=1&c5=1&c6=1&c7=1&",
        "music": "c23=1&c24=1&c25=1&c26=1&c17=1&",
        "games": "c43=1&c10=1&",
        "anime": "c28=1&",
        "software": "c20=1&c21=1&c18=1&",
        "pictures": "c37=1&",
        "books": "c13=1&c19=1&c12=1&c14=1&c15=1&",
    }

    class TorrentGalaxyParser(HTMLParser):
        DIV: str = "div"
        A: str = "a"
        SPAN: str = "span"
        FONT: str = "font"
        SMALL: str = "small"
        count_div: int = -1
        get_size: bool = False
        get_seeds: bool = False
        get_leechs: bool = False
        get_pub_date0: bool = False
        get_pub_date: bool = False
        url: str = "https://torrentgalaxy.to"

        def __init__(self):
            HTMLParser.__init__(self)
            self.count_div = -1
            self.get_size = False
            self.get_seeds = False
            self.get_leechs = False
            self.get_pub_date0 = False
            self.get_pub_date = False
            self.this_record: dict[str, str] = {}

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            if tag == self.DIV:
                my_attrs = dict(attrs)
                # if (my_attrs.get('class') == 'tgxtablerow txlight'):
                if my_attrs.get("class") and "tgxtablerow" in (my_attrs.get("class") or ""):
                    self.count_div = 0
                    self.this_record = {}
                    self.this_record["engine_url"] = self.url
                if (
                    my_attrs.get("class")
                    and ("tgxtablecell" in (my_attrs.get("class") or ""))
                    and self.count_div >= 0
                ):
                    self.count_div += 1
                if (
                    my_attrs.get("style")
                    and ("text-align:right" in (my_attrs.get("style") or ""))
                    and self.count_div >= 0
                ):
                    self.get_pub_date0 = True

            if tag == self.A and self.count_div < 13:
                my_attrs = dict(attrs)
                if (
                    "title" in my_attrs
                    and ("class" in my_attrs)
                    and "txlight" in (my_attrs.get("class") or "")
                    and not my_attrs.get("id")
                ):
                    self.this_record["name"] = my_attrs["title"] or ""
                    self.this_record["desc_link"] = self.url + (my_attrs["href"] or "")
                if "role" in my_attrs and my_attrs.get("role") == "button":
                    self.this_record["link"] = my_attrs["href"] or ""

            if tag == self.SPAN:
                my_attrs = dict(attrs)
                if "class" in my_attrs and "badge badge-secondary" in (my_attrs.get("class") or ""):
                    self.get_size = True

            if tag == self.FONT:
                my_attrs = dict(attrs)
                if my_attrs.get("color") == "green":
                    self.get_seeds = True
                elif my_attrs.get("color") == "#ff0000":
                    self.get_leechs = True

            if self.count_div == 13 and tag == self.SMALL:
                record = self.this_record
                result = SearchResults(
                    link=record.get("link") or "",
                    name=record.get("name") or "",
                    size=int(record.get("size") or 0),
                    seeds=int(record.get("seeds") or 0),
                    leech=int(record.get("leech") or 0),
                    engine_url=record.get("engine_url") or "",
                )
                pub_date = record.get("pub_date")
                if pub_date is not None:
                    result["pub_date"] = int(pub_date)
                _qbt_prettyPrinter(result)
                self.this_record = {}
                self.count_div = -1

            if self.get_pub_date0 and tag == self.SMALL:
                self.get_pub_date = True

        @override
        def handle_data(self, data: str):
            if self.get_size is True and self.count_div < 13:
                self.this_record["size"] = data.strip().replace(",", "")
                self.get_size = False
            if self.get_seeds is True:
                self.this_record["seeds"] = data.strip().replace(",", "")
                self.get_seeds = False
            if self.get_leechs is True:
                self.this_record["leech"] = data.strip().replace(",", "")
                self.get_leechs = False
            if self.get_pub_date is True:
                self.this_record["pub_date"] = str(
                    int(time.mktime(time.strptime(data.strip(), "%d/%m/%y %H:%M")))
                )
                self.get_pub_date, self.get_pub_date0 = False, False

    def do_search(self, url: str):
        webpage = retrieve_url(url)
        tgParser = self.TorrentGalaxyParser()
        tgParser.feed(webpage)

    def search(self, what: str, cat: str = "all"):
        query = str(what).replace(r" ", "+")
        search_url = "https://torrentgalaxy.to/torrents.php?"
        full_url = (
            search_url
            + self.supported_categories[cat.lower()]
            + "sort=seeders&order=desc&search="
            + query
        )

        webpage = retrieve_url(full_url)
        tgParser = self.TorrentGalaxyParser()
        tgParser.feed(webpage)

        all_results_re = re.compile(r"steelblue[^>]+>(.*?)<")
        all_result_matches = cast(list[str], all_results_re.findall(webpage))
        if not all_result_matches:
            return
        all_results = all_result_matches[0]
        all_results = all_results.replace(" ", "")
        pages = math.ceil(int(all_results) / 50)
        jobs: list[tuple[str]] = []
        for page in range(1, min(pages, MAX_PAGES)):
            this_url = full_url + "&page=" + str(page)
            jobs.append((this_url,))
        _ = _qbt_run_parallel(self.do_search, jobs, _qbt_new_deadline())


if __name__ == "__main__":
    a = torrentgalaxy()
    a.search("ncis new", "all")
