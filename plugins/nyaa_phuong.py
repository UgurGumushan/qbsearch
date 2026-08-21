# VERSION: 1.03
"""
Sukebei Nyaa adult anime search. Scrapes the HTML results table and follows
the pagination, reading the total count from the "Displaying results 1-N out
of M results" footer line.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
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


# some other imports if necessary
class nyaa_phuong:
    url = "https://sukebei.nyaa.si"
    name = "Sukebei Nyaa"  # spaces and special characters are allowed here
    # Which search categories are supported by this search engine and their corresponding id
    # Possible categories are ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "6",
        "tv": "4",
        "music": "1",
        "games": "2",
        "anime": "7",
        "software": "3",
    }

    def __init__(self) -> None:
        pass

    class RowParser(HTMLParser):
        """Collects the <tr> rows of the results table.

        Each row is a list of cells; each cell is (text, [hrefs]) so the
        anchor hrefs inside a <td> are preserved (the original bs4 code read
        a.get('href'), not the cell text)."""

        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.rows: list[list[tuple[str, list[str]]]] = []
            self.in_results: bool = False
            self.depth: int = 0
            self.cur: list[tuple[str, list[str]]] | None = None
            self.cell: tuple[str, list[str]] | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if tag == "table":
                self.depth += 1
                if not self.in_results and "results" in (params.get("class") or ""):
                    self.in_results = True
                return
            if not self.in_results:
                return
            if tag == "tr":
                self.cur = []
            elif tag == "td" and self.cur is not None:
                self.cell = ("", [])
            elif tag == "a" and self.cell is not None:
                href = params.get("href")
                if href is not None:
                    self.cell[1].append(href)

        def handle_data(self, data: str) -> None:
            if self.cell is not None:
                self.cell = (self.cell[0] + data, self.cell[1])

        def handle_endtag(self, tag: str) -> None:
            if not self.in_results:
                return
            if tag == "td" and self.cell is not None and self.cur is not None:
                self.cur.append(self.cell)
                self.cell = None
            elif tag == "tr" and self.cur is not None:
                self.rows.append(self.cur)
                self.cur = None
            elif tag == "table":
                self.depth -= 1
                if self.depth <= 0:
                    self.in_results = False

    @staticmethod
    def _cell_text(cell: tuple[str, list[str]]) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cell[0])).strip()

    @staticmethod
    def _first_href(cell: tuple[str, list[str]]) -> str:
        return cell[1][0] if cell[1] else ""

    @staticmethod
    def _last_href(cell: tuple[str, list[str]]) -> str:
        return cell[1][-1] if cell[1] else ""

    @staticmethod
    def _size_bytes(raw: str) -> int:
        m = re.search(r"([\d.]+)\s*([A-Za-z]+)", raw)
        if not m:
            return 0
        value = float(m.group(1))
        unit = m.group(2)
        if unit == "GiB":
            return int(value * 1073741824)
        if unit == "MiB":
            return int(value * 1000000)
        return 0

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = "all") -> None:
        # what is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        # cat is the name of a search category in ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
        # q - query, f - filter, c - category
        base_url = "https://sukebei.nyaa.si/?q=%s&f=0&c=0_0"
        base_url_with_query = base_url % what
        response = retrieve_url(base_url_with_query)
        info = re.search(r"Displaying results 1-(\d+) out of (\d+) results", response)
        item_per_pages = info.group(1) if info else "75"
        total_results = info.group(2) if info else "0"
        number_of_page = (
            math.ceil(float(total_results) / float(item_per_pages)) if item_per_pages != "0" else 1
        )
        for i in range(min(int(number_of_page), MAX_PAGES)):
            base_url_with_query_and_page = base_url_with_query + f"&p={i + 1!s}"
            response = retrieve_url(base_url_with_query_and_page)
            parser = self.RowParser()
            parser.feed(response)
            parser.close()
            for tds in parser.rows:
                if len(tds) < 7:
                    continue
                ref = self._first_href(tds[1])
                title = self._cell_text(tds[1])
                link = self._last_href(tds[2])
                sizeInBytes = self._size_bytes(self._cell_text(tds[3]))
                seeders = self._cell_text(tds[5])
                leechers = self._cell_text(tds[6])
                try:
                    pub_date = int(
                        datetime.strptime(
                            self._cell_text(tds[4]), "%Y-%m-%d %H:%M"
                        )
                        .replace(tzinfo=timezone.utc)
                        .timestamp()
                    )
                except ValueError:
                    pub_date = -1
                try:
                    seeds = int(seeders)
                except ValueError:
                    seeds = -1
                try:
                    leech = int(leechers)
                except ValueError:
                    leech = -1
                res: SearchResults = {
                    "link": link,
                    "name": title,
                    "size": str(sizeInBytes),
                    "seeds": seeds,
                    "leech": leech,
                    "engine_url": self.url,
                    "desc_link": self.url + ref,
                    "pub_date": pub_date,
                }
                _qbt_prettyPrinter(res)
