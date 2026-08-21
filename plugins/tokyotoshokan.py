# VERSION: 2.3
"""
Tokyo Toshokan (http://tokyotosho.info, anime site) search engine. Scrapes
the listing table; further pages are followed via ?lastid=&page= links found
in the last page, batched five pages at a time.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from re import compile as re_compile

from helpers import download_file
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


def stats_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return -1


class tokyotoshokan:
    url: str = "http://tokyotosho.info"
    name: str = "Tokyo Toshokan"

    global page_count
    page_count = 1

    def __init__(self):
        self.supported_categories: dict[str, str] = {"all": "0", "anime": "1", "games": "14"}
        # self.supported_categories = {'all': '0', 'anime': '1', 'anime(non-english)': '10',
        #                        'manga': '3', 'drama': '8', 'music': '2',
        #                        'music video': '9', 'raw': '7', 'hentai': '4',
        #                        'eroge': '14', 'batch': '11', 'jav': '15', 'other': '5'}
        #

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    class MyHtmlParseWithBlackJack(HTMLParser):
        def __init__(self, url: str):
            HTMLParser.__init__(self)
            self.get_size_regex: re.Pattern[str] = re_compile(r".*Size:\s+([^ ]*)\s+.*")
            self.url: str = url
            self.current_item: dict[str, str] | None = None
            self.size_found: bool = False
            self.name_found: bool = False
            self.stats_found: bool = False
            self.stat_name: str | None = None

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if self.current_item:
                if tag == "a":
                    href: str | None = params.get("href")
                    if isinstance(href, str) and href.startswith("magnet"):
                        self.current_item["link"] = href
                    elif "type" in params and params["type"] == "application/x-bittorrent":
                        self.name_found = True
                        self.current_item["name"] = ""
                    elif isinstance(href, str) and href.startswith("details"):
                        self.current_item["desc_link"] = f"{self.url}/{href}"

                elif tag == "td" and "class" in params:
                    if params.get("class") == "desc-bot":
                        self.size_found = True
                        self.current_item["size"] = "Unknown"
                    elif params.get("class") == "stats":
                        self.stats_found = True

                elif self.stats_found and tag == "span":
                    self.stat_name = "leech" if "seeds" in self.current_item else "seeds"

            elif tag == "tr" and (params.get("class") or "").find("category"):
                self.current_item = {}
                self.current_item["engine_url"] = self.url

        @override
        def handle_endtag(self, tag: str) -> None:
            if tag == "a":
                if self.name_found:
                    self.name_found = False
            elif tag == "span":
                self.stat_name = None
            elif self.current_item and tag == "tr" and len(self.current_item) >= 7:
                raw = self.current_item
                res: SearchResults = {
                    "link": raw["link"],
                    "name": raw["name"],
                    "size": raw["size"],
                    "seeds": stats_int(raw["seeds"]),
                    "leech": stats_int(raw["leech"]),
                    "engine_url": raw["engine_url"],
                    "desc_link": raw["desc_link"],
                }
                if "pub_date" in raw:
                    res["pub_date"] = int(raw["pub_date"])
                _qbt_prettyPrinter(res)
                self.current_item = None
                self.size_found = False
                self.name_found = False
                self.stats_found = False
                self.stat_name = None

        @override
        def handle_data(self, data: str) -> None:
            if self.current_item is None:
                return
            if self.name_found:
                self.current_item["name"] += data
            elif self.size_found:
                # There can be several pieces.
                result = self.get_size_regex.search(data)
                if result:
                    self.current_item["size"] = result.group(1)
                    self.size_found = False
                date_match = re_compile(r"Date:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+UTC").search(
                    data
                )
                if date_match:
                    self.current_item["pub_date"] = str(
                        int(
                            datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M")
                            .replace(tzinfo=timezone.utc)
                            .timestamp()
                        )
                    )
            elif self.stat_name:
                self.current_item[self.stat_name] = data

    def handle_more_pages(
        self,
        last_page_url: str,
        parser: MyHtmlParseWithBlackJack,
        query: str,
        skip_first: bool = False,
    ) -> str:
        torrent_list = re_compile('(?s)<table class="listing">(.*)</table>')
        additional_links = re_compile(
            r"\?lastid=[0-9]+&page=[0-9]+&terms={}".format(query.replace("%20", "\\+"))
        )

        data: str = retrieve_url(last_page_url)
        m = torrent_list.search(data)
        if m:
            data = m.group(0)

        for res_link in (
            "".join((self.url, "/search.php", link.group(0)))
            for link in additional_links.finditer(data)
        ):
            if skip_first:
                skip_first = False
                continue

            global page_count
            page_count += 1
            last_page_url = res_link
            data = retrieve_url(res_link)
            m = torrent_list.search(data)
            if m:
                data = m.group(0)
            parser.feed(data)
            parser.close()

        return last_page_url

    def search(self, query: str, cat: str = "all") -> None:
        query = query.replace(" ", "+")
        parser = self.MyHtmlParseWithBlackJack(self.url)
        last_page_url = ""
        page_multiplier = 1
        torrent_list = re_compile('(?s)<table class="listing">(.*)</table>')
        request_url = f"{self.url}/search.php?terms={query}&type={self.supported_categories[cat]}&size_min=&size_max=&username="
        data: str = retrieve_url(request_url)

        m = torrent_list.search(data)
        if m:
            data = m.group(0)
        parser.feed(data)
        parser.close()

        last_page_url = self.handle_more_pages(request_url, parser, query)

        for _ in range(MAX_PAGES):
            if page_count > (page_multiplier * 5):
                last_page_url = self.handle_more_pages(last_page_url, parser, query, True)
                page_multiplier += 1
            else:
                break
