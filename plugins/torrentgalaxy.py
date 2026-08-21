# VERSION: 0.08
"""
TorrentGalaxy (https://torrentgalaxy.to) search engine. Scrapes rows of
tgxtablerow/tgxtablecell divs, using cell class and text alignment to decide
which field (name, size, seeds, leeches, pub date) the text belongs to.
"""

import math
import re
import time
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


class torrentgalaxy:
    url = "https://torrentgalaxy.to"
    name = "TorrentGalaxy"
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
        (
            DIV,
            A,
            SPAN,
            FONT,
            SMALL,
        ) = "div", "a", "span", "font", "small"
        count_div = -1
        get_size = False
        get_seeds = False
        get_leechs = False
        get_pub_date0 = False
        get_pub_date = False
        url = "https://torrentgalaxy.to"

        def __init__(self):
            HTMLParser.__init__(self)
            self.count_div = -1
            self.get_size = False
            self.get_seeds = False
            self.get_leechs = False
            self.get_pub_date0 = False
            self.get_pub_date = False
            self.this_record: dict[str, str] = {}

        def handle_starttag(self, tag: str, attrs):
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

        def handle_data(self, data):
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

    def search(self, what: str, cat="all"):
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
        all_result_matches = all_results_re.findall(webpage)
        if not all_result_matches:
            return
        all_results = all_result_matches[0]
        all_results = all_results.replace(" ", "")
        pages = math.ceil(int(all_results) / 50)
        jobs = []
        for page in range(1, min(pages, MAX_PAGES)):
            this_url = full_url + "&page=" + str(page)
            jobs.append((this_url,))
        _qbt_run_parallel(self.do_search, jobs, _qbt_new_deadline())


if __name__ == "__main__":
    a = torrentgalaxy()
    a.search("ncis new", "all")
