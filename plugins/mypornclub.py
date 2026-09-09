# VERSION: 1.1
"""
MyPorn Club adult search. Fetches every paginated result page (threaded) and
reads each torrent's detail page for its magnet link, appending a computed
web-seed (&ws=) when the torrent advertises one.
"""

from __future__ import annotations

import base64
import json
import re
from html.parser import HTMLParser
from typing import ClassVar, TypedDict, cast

from helpers import download_file
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


class MyPornRow(TypedDict, total=False):
    link: str
    name: str
    size: str
    seeds: int
    leech: int
    engine_url: str
    desc_link: str
    pub_date: int


class mypornclub:
    url: str = "https://myporn.club"
    name: str = "MyPorn Club"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    pagination_regex: str = r"<div>Page\s+\d+\s+of\s+(\d+)</div>"

    class MyHtmlParser(HTMLParser):
        def error(self, _message: str):
            pass

        DIV: str = "div"
        A: str = "a"
        SPAN: str = "span"
        I: str = "i"
        B: str = "b"

        def __init__(
            self,
            url: str,
            detail_budget: list[int] | None = None,
            detail_lock: object | None = None,
            detail_links: set[str] | None = None,
            result_links: set[str] | None = None,
        ) -> None:
            HTMLParser.__init__(self)
            self.url: str = url
            self.row: MyPornRow = {}
            self.detail_budget = detail_budget if detail_budget is not None else [MAX_DETAILS]
            self.detail_lock = detail_lock if detail_lock is not None else _qbt_Lock()
            self.detail_links = detail_links if detail_links is not None else set()
            self.result_links = result_links if result_links is not None else set()

            self.foundResults: bool = False
            self.insideRow: bool = False
            self.insideTorrentData: bool = False
            self.insideTorrentName: bool = False
            self.insideMetaData: bool = False
            self.insideLabelCell: bool = False
            self.insideSizeCell: bool = False
            self.insideSeedCell: bool = False
            self.insideLeechCell: bool = False
            self.shouldAddBrackets: bool = False
            self.shouldAddName: bool = False
            self.web_seed: str | None = None
            self.shouldGetDate: bool = False
            self.magnet_regex: str = r'href=["\']magnet:.+?["\']'
            self.has_web_regex: str = r"(sxyprn\.com[^\w]*?post[^\w]*?[\w]*?\.html)"

        def _claim_detail(self, link: str | None = None) -> bool:
            with self.detail_lock:
                if link is not None and link in self.detail_links:
                    return False
                if self.detail_budget[0] <= 0:
                    return False
                if link is not None:
                    self.detail_links.add(link)
                self.detail_budget[0] -= 1
                return True

        def _claim_result(self, link: str) -> bool:
            with self.detail_lock:
                if link in self.result_links:
                    return False
                self.result_links.add(link)
                return True

        def preda(self, arg: list[str]) -> list[str]:
            adjusted = int(arg[5])
            adjusted -= self.ssut51(arg[6]) + self.ssut51(arg[7])
            arg[5] = str(adjusted)
            return arg

        def ssut51(self, arg: str) -> int:
            # Digit sum of the argument; part of the web-seed signature
            str_num = "".join(filter(str.isdigit, arg))
            sut = 0
            for char in str_num:
                sut += int(char)
            return sut

        def boo(self, ss: str, es: str) -> str:
            # urlsafe-base64 of "digit_sum(sxyprn.com)-digit_sum(...)"; part of
            # the web-seed signature
            b = base64.b64encode((ss + "-" + "sxyprn.com" + "-" + es).encode()).decode()
            return b.replace("+", "-").replace("/", "_").replace("=", ".")

        def check_for_web_seed(self, web_page_url: str) -> str | None:
            page_id = web_page_url.split("/")[-1].split(".")[0]
            web_page_url = re.sub(r"\\", r"", web_page_url)
            if not self._claim_detail(web_page_url):
                return None
            page = retrieve_url(web_page_url)
            match = re.search(r'data-vnfo=(["\'])(?P<data>{.+?})\1', page)
            if match:
                try:
                    data1_value: object = cast(object, json.loads(match.group("data")))
                except (TypeError, ValueError):
                    return None
                if not isinstance(data1_value, dict):
                    return None
                data1 = cast(dict[str, object], cast(object, data1_value))
                raw_parts = data1.get(page_id)
                if not isinstance(raw_parts, str):
                    return None
                parts = raw_parts.split("/")
                if len(parts) < 8:
                    return None
                parts[1] += (
                    "8" + "/" + self.boo(str(self.ssut51(parts[6])), str(self.ssut51(parts[7])))
                )
                parts = self.preda(parts)
                final_url = "https://sxyprn.com" + "/".join(parts)

                with _qbt_safe_urlopen(final_url) as response:
                    return "&ws=" + final_url + "&ws=" + response.geturl()

            else:
                return None

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = {key: value for key, value in attrs if value is not None}
            cssClasses = params.get("class") or ""
            if "torrents_list" in cssClasses:
                self.foundResults = True
                return

            if self.foundResults and "torrent_element" in cssClasses and tag == self.DIV:
                self.insideRow = True
                if self.insideRow and "torrent_element_text_div" in cssClasses and tag == self.DIV:
                    self.insideTorrentData = True

                if self.insideRow and "torrent_element_info" in cssClasses and tag == self.DIV:
                    self.insideMetaData = True
                return

            if (
                self.insideTorrentData
                and "torrent_element_text_span" in cssClasses
                and tag == self.SPAN
            ):
                self.row["name"] = ""
                self.insideTorrentName = True
                self.shouldAddName = True

            if self.insideTorrentName and tag == self.B:
                self.shouldAddBrackets = True

            if self.insideTorrentName and tag == self.I:
                self.shouldAddBrackets = False
                self.shouldAddName = False

            if self.insideMetaData and "linkadd" in cssClasses and tag == self.A:
                self.shouldGetDate = True

            if self.insideTorrentData and tag == self.A and "uploader_tel" not in cssClasses:
                href = params.get("href")
                if href is None:
                    return
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                if not self._claim_detail(link):
                    return
                torrent_page = retrieve_url(link)
                magnet_match = re.search(self.magnet_regex, torrent_page, re.MULTILINE)
                # Use the first magnet found on the detail page
                if magnet_match is None:
                    # Some live pages are removed or replaced by an HTML
                    # interstitial before they expose a magnet link.
                    self.row = {}
                    self.insideRow = False
                    self.insideTorrentData = False
                    self.insideTorrentName = False
                    self.insideMetaData = False
                    return
                self.row["link"] = magnet_match.group().replace("'", '"').split('"')[1]

                has_page_match = re.search(self.has_web_regex, torrent_page, re.MULTILINE)
                if has_page_match:
                    has_page = "https://" + has_page_match.group(1)
                    self.web_seed = self.check_for_web_seed(has_page)
                    if self.web_seed:
                        self.row["link"] = self.row["link"] + self.web_seed

                return

            if self.insideMetaData and "teis" in cssClasses:
                self.insideLabelCell = True

        @override
        def handle_data(self, data: str) -> None:

            if self.shouldGetDate:
                self.shouldGetDate = False
                from datetime import datetime

                if len(data.split(" ")) == 3 and data.split(" ")[2] == "ago":
                    if data.split(" ")[1] == "minutes":
                        self.row["pub_date"] = int(
                            datetime.now().timestamp() - (int(data.split(" ")[0]) * 60)
                        )
                    if data.split(" ")[1] == "hours":
                        self.row["pub_date"] = int(
                            datetime.now().timestamp() - (int(data.split(" ")[0]) * 60 * 60)
                        )
                    if data.split(" ")[1] == "days":
                        self.row["pub_date"] = int(
                            datetime.now().timestamp() - (int(data.split(" ")[0]) * 60 * 60 * 24)
                        )
                    if data.split(" ")[1] == "months":
                        self.row["pub_date"] = int(
                            datetime.now().timestamp()
                            - (int(data.split(" ")[0]) * 60 * 60 * 24 * 30)
                        )
                    if data.split(" ")[1] == "years":
                        self.row["pub_date"] = int(
                            datetime.now().timestamp()
                            - (int(data.split(" ")[0]) * 60 * 60 * 24 * 365)
                        )

            if self.insideRow:
                if self.insideTorrentData and self.insideTorrentName:
                    if self.shouldAddBrackets:
                        self.row["name"] = f"{self.row.get('name') or ''}[{data}]".strip()
                        self.shouldAddBrackets = False
                        return
                    if self.shouldAddName:
                        self.row["name"] = f"{self.row.get('name') or ''} {data}".strip()
                        return

                if self.insideMetaData:
                    if self.insideSizeCell:
                        size = data.replace(",", ".")
                        self.row["size"] = size
                        self.insideSizeCell = False
                        self.insideLabelCell = False

                    if self.insideSeedCell:
                        try:
                            self.row["seeds"] = int(data)
                        except ValueError:
                            self.row["seeds"] = -1
                        self.insideSeedCell = False
                        self.insideLabelCell = False

                    if self.insideLeechCell:
                        try:
                            self.row["leech"] = int(data)
                        except ValueError:
                            self.row["leech"] = -1
                        self.insideLeechCell = False
                        self.insideLabelCell = False

                    if self.insideLabelCell:
                        if data == "[size]:":
                            self.insideSizeCell = True
                        if data == "[seeders]:":
                            self.insideSeedCell = True
                        if data == "[leechers]:":
                            self.insideLeechCell = True

        @override
        def handle_endtag(self, tag: str) -> None:
            if self.insideRow and tag == self.DIV:
                if self.insideTorrentData and tag == self.DIV:
                    self.insideTorrentData = False
                    self.insideTorrentName = False
                    return

                if self.insideMetaData and tag == self.DIV:
                    self.insideMetaData = False
                    return

                self.row["engine_url"] = self.url

                if self.web_seed:
                    self.row["name"] = "💥 " + (self.row.get("name") or "")
                    self.web_seed = None

                if all(field in self.row for field in ("link", "name", "size", "seeds", "leech")):
                    result = cast(SearchResults, cast(object, self.row))
                    if self._claim_result(str(result["link"])):
                        _qbt_prettyPrinter(result)
                self.row = {}
                self.insideRow = False

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def do_search(
        self,
        page: int,
        what: str,
        detail_budget: list[int] | None = None,
        detail_lock: object | None = None,
        detail_links: set[str] | None = None,
        result_links: set[str] | None = None,
    ) -> None:
        parser = self.MyHtmlParser(
            self.url, detail_budget, detail_lock, detail_links, result_links
        )
        page_url = f"{self.url}/s/{what}/seeders/{page}"
        retrievedHtml = retrieve_url(page_url)
        parser.feed(retrievedHtml)
        parser.close()

    def search(self, what: str, _cat: str = "all") -> None:
        deadline = _qbt_new_deadline()
        detail_budget = [MAX_DETAILS]
        detail_lock = _qbt_Lock()
        detail_links: set[str] = set()
        result_links: set[str] = set()
        parser = self.MyHtmlParser(
            self.url, detail_budget, detail_lock, detail_links, result_links
        )
        what = what.replace("%20", "-")
        what = what.replace(" ", "-")
        page = 1

        page_url = f"{self.url}/s/{what}/seeders/{page}"
        retrievedHtml = retrieve_url(page_url)
        pagination_match = re.search(self.pagination_regex, retrievedHtml, re.MULTILINE)
        parser.feed(retrievedHtml)
        parser.close()
        if pagination_match is None:
            return
        try:
            last_page = int(pagination_match.group(1))
        except (IndexError, ValueError):
            return
        page += 1

        jobs = [
            (p, what, detail_budget, detail_lock, detail_links, result_links)
            for p in range(page, min(last_page, MAX_PAGES) + 1)
        ]
        _ = _qbt_run_parallel(self.do_search, jobs, deadline)
