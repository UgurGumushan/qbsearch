# VERSION: 2.2
"""Cpasbien (French) engine: movies and TV torrents.

The current site domain is pulled from a public URL file since the site
moves often; sizes arrive in French units (ex. 'Ko') which are converted.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar, cast

import helpers
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


headers = cast(dict[str, str], cast(object, vars(helpers)["_headers"]))

logger = logging.getLogger()


class cpasbien:
    # This is a fake url only for engine associations in file download
    url: str = "http://www.cpasbien.fr"
    name: str = "Cpasbien (french)"
    results_per_page: int = 50
    supported_categories: ClassVar[dict[str, list[str]]] = {"all": [""]}

    def __init__(self) -> None:
        self.real_url: str = self.find_url()
        logger.debug("Cpasbien URL: %s", self.real_url)

    def find_url(self) -> str:
        """Fetch the current site domain from a GitHub URL file so the engine
        keeps working when the domain moves."""
        link_github = "https://raw.githubusercontent.com/MarcBresson/cpasbien/master/cpasbien.url"
        content: str = ""
        try:
            req = urllib.request.Request(link_github, headers=headers)
            with _qbt_safe_urlopen(req) as response:
                content = response.read().decode()
            cpasbien_url = content.strip()
            return cpasbien_url or "http://www.cpasbien.biz"

        except urllib.error.URLError as e:
            default_url = "http://www.cpasbien.biz"

            if str(e.reason).lower() == "not found":
                logger.warning(
                    "Could not find URL '%s', defaulting to '%s'", link_github, default_url
                )
            else:
                logger.warning(
                    "Error '%s' while tring to find the current cpasbien URL, defaulting to '%s'",
                    e.reason,
                    default_url,
                )
            return default_url

    def download_torrent(self, desc_link: str) -> None:
        """find the link to the torrent"""
        logger.debug("Looking for the torrent download link at URL %s", desc_link)
        req = urllib.request.Request(desc_link, headers=headers)
        content: str = ""

        try:
            with _qbt_safe_urlopen(req) as response:
                content = response.read().decode()
        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return
        if not content:
            return

        links = cast(list[str], re.findall(r'<a href="(/get_torrent/.*?)">', content))
        link = self.real_url + links[0]
        logger.info("Found torrent download link with URL %s", link)

        print(download_file(link))

    def search(self, what: str, _cat: str | None = None) -> None:
        results: list[SearchResults] = []
        len_old_result = 0
        for page in range(10):
            url = f"{self.real_url}/recherche/{what}/{page * self.results_per_page + 1}"

            parser = TableRowExtractor(self.real_url, self.url, results)

            try:
                data = retrieve_url(url)
            except urllib.error.URLError as errno:
                print(" ".join(("Connection error:", str(errno.reason))))
                break

            parser.feed(data)
            results.extend(parser.results)
            parser.close()

            # if there is no new result on the page, stop the search
            if len(results) - len_old_result == 0:
                break

            len_old_result = len(results)

        # Sort results
        good_order = [
            ord_res
            for _, ord_res in sorted(
                zip(
                    [[int(res["seeds"]), int(res["leech"])] for res in results], range(len(results))
                )
            )
        ]
        results = [results[x] for x in good_order[::-1]]

        logger.info("found %d torrents from cpasbien search engine", len(results))

        # Add engine
        for res in results:
            res["engine_url"] = self.url
        # Print
        for res in results:
            _qbt_prettyPrinter(res)


class TableRowExtractor(HTMLParser):
    map_name: dict[str, str]
    current_div_class: str = ""

    def __init__(self, url: str, engine_url: str, results: list[SearchResults]):
        self.results: list[SearchResults] = results
        self.map_name = {"titre": "name", "poid": "size", "up": "seeds", "down": "leech"}
        self.in_tr: bool = False
        self.in_table_corps: bool = False
        self.in_div_or_anchor: bool = False
        self.current_row: dict[str, str] = {}
        self.url: str = url
        self.engine_url: str = engine_url
        super().__init__()

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag == "table":
            # Only the results table (class "table-corps") is parsed.
            attrs_dict = dict(attrs)
            if attrs_dict.get("class") == "table-corps":
                self.in_table_corps = True

        if self.in_table_corps and tag == "tr":
            self.in_tr = True

        if self.in_tr and tag in ["div", "a"]:
            # Map the cell's class ("titre", "poid", "up", "down") to a result
            # field so the following text lands in the right column.
            self.in_div_or_anchor = True
            attrs_dict = dict(attrs)
            self.current_div_class = self.map_name.get(attrs_dict.get("class") or "", "")
            if tag == "a" and self.current_div_class == "name":
                href = attrs_dict.get("href")
                if href is not None:
                    self.current_row["link"] = self.url + href
                    self.current_row["desc_link"] = self.url + href

    @override
    def handle_endtag(self, tag: str):
        if tag == "tr":
            if (
                self.in_table_corps
                and "desc_link" in self.current_row
                and self.current_row["desc_link"]
                not in [res.get("desc_link") for res in self.results]
            ):
                self.results.append(
                    SearchResults(
                        link=self.current_row["link"],
                        name=self.current_row["name"],
                        size=unit_fr2en(self.current_row["size"]),
                        seeds=int(self.current_row["seeds"]),
                        leech=int(self.current_row["leech"]),
                        engine_url=self.engine_url,
                        desc_link=self.current_row["desc_link"],
                    )
                )
            self.in_tr = False

            self.current_row = {}
        if tag == "table":
            self.in_table_corps = False
        if tag in ["div", "a"]:
            self.in_div_or_anchor = False

    @override
    def handle_data(self, data: str):
        if self.in_div_or_anchor and self.current_div_class:
            self.current_row[self.current_div_class] = data

    def get_rows(self) -> list[SearchResults]:
        return self.results


def unit_fr2en(size: str) -> str:
    """Convert French size units (Ko, Mo, ...) to English (KB, MB, ...)."""
    return re.sub(r"([KMGTP])o", lambda match: match.group(1) + "B", size, flags=re.IGNORECASE)
