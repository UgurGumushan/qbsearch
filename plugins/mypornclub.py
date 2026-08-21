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
    url = "https://myporn.club"
    name = "MyPorn Club"
    supported_categories: ClassVar[dict[str, str]]  = {"all": "all"}

    pagination_regex = r"<div>Page\s\d\sof\s\d+</div>"

    class MyHtmlParser(HTMLParser):
        def error(self, message):
            pass

        DIV, A, SPAN, I, B = ("div", "a", "span", "i", "b")

        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.row: MyPornRow = {}
            self.rows: list[MyPornRow] = []

            self.foundResults = False
            self.insideRow = False
            self.insideTorrentData = False
            self.insideTorrentName = False
            self.insideMetaData = False
            self.insideLabelCell = False
            self.insideSizeCell = False
            self.insideSeedCell = False
            self.insideLeechCell = False
            self.shouldAddBrackets = False
            self.shouldAddName = False
            self.web_seed: str | None = None
            self.shouldGetDate = False
            self.magnet_regex = r'href=["\']magnet:.+?["\']'
            self.has_web_regex = (
                r"(sxyprn\.com[^\w]*?post[^\w]*?[\w]*?\.html)"
            )

        def preda(self, arg: list[str]) -> list[str]:
            adjusted = int(arg[5])
            adjusted -= self.ssut51(arg[6]) + self.ssut51(arg[7])
            arg[5] = str(adjusted)
            return arg

        def ssut51(self, arg: str) -> int:
            # Digit sum of the argument; part of the web-seed signature
            str_num = ''.join(filter(str.isdigit, arg))
            sut = 0
            for char in str_num:
                sut += int(char)
            return sut

        def boo(self, ss: str, es: str) -> str:
            # urlsafe-base64 of "digit_sum(sxyprn.com)-digit_sum(...)"; part of
            # the web-seed signature
            b = base64.b64encode((ss + "-" + "sxyprn.com" + "-" + es).encode()).decode()
            return b.replace('+', '-').replace('/', '_').replace('=', '.')

        def check_for_web_seed(self, web_page_url: str) -> str | None:
            id = web_page_url.split("/")[-1].split(".")[0]
            web_page_url = re.sub(r'\\', r'', web_page_url)
            page = retrieve_url(web_page_url)
            match = re.search(r'data-vnfo=(["\'])(?P<data>{.+?})\1', page)
            if match:
                data1 = json.loads(match.group("data"))
                parts = data1[id].split("/")
                parts[1] += "8" + "/" + self.boo(str(self.ssut51(parts[6])), str(self.ssut51(parts[7])))
                parts = self.preda(parts)
                final_url = 'https://sxyprn.com' + "/".join(parts)

                with _qbt_safe_urlopen(final_url) as response:
                    return "&ws=" + final_url + "&ws=" + response.geturl()
                       
            else:
                return None

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            params = {key: value for key, value in attrs if value is not None}
            cssClasses = params.get("class") or ""
            if "torrents_list" in cssClasses:
                self.foundResults = True
                return

            if (
                self.foundResults
                and "torrent_element" in cssClasses
                and tag == self.DIV
            ):
                self.insideRow = True
                if (
                    self.insideRow
                    and "torrent_element_text_div" in cssClasses
                    and tag == self.DIV
                ):
                    self.insideTorrentData = True

                if (
                    self.insideRow
                    and "torrent_element_info" in cssClasses
                    and tag == self.DIV
                ):
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
            
            if self.insideMetaData and 'linkadd' in cssClasses and tag == self.A:
                    self.shouldGetDate = True

            if (
                self.insideTorrentData
                and tag == self.A
                and "uploader_tel" not in cssClasses
            ):
                href = params.get("href")
                if href is None:
                    return
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                torrent_page = retrieve_url(link)
                matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                magnet_urls = [x.group() for x in matches]
                # Use the first magnet found on the detail page
                if not magnet_urls:
                    # Some live pages are removed or replaced by an HTML
                    # interstitial before they expose a magnet link.
                    self.row = {}
                    self.insideRow = False
                    self.insideTorrentData = False
                    self.insideTorrentName = False
                    self.insideMetaData = False
                    return
                self.row["link"] = magnet_urls[0].replace("'", '"').split('"')[1]

                _has_page = re.finditer(self.has_web_regex, torrent_page, re.MULTILINE)
                has_page = ["https://" + x.group(1) for x in _has_page]
                if has_page:
                    self.web_seed = self.check_for_web_seed(has_page[0])
                    if self.web_seed:
                        self.row["link"] = self.row["link"] + self.web_seed

                return

            if self.insideMetaData and "teis" in cssClasses:
                self.insideLabelCell = True

        def handle_data(self, data: str) -> None:

            if self.shouldGetDate:
                self.shouldGetDate = False
                from datetime import datetime
                if len(data.split(' ')) == 3 and data.split(' ')[2] == 'ago':
                    if data.split(' ')[1] == 'minutes':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60))
                    if data.split(' ')[1] == 'hours':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60))
                    if data.split(' ')[1] == 'days':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60 * 24))
                    if data.split(' ')[1] == 'months':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60 * 24 * 30))
                    if data.split(' ')[1] == 'years':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60 * 24 * 365))
                    
                    

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

                if all(
                    field in self.row
                    for field in ("link", "name", "size", "seeds", "leech")
                ):
                    _qbt_prettyPrinter(cast(SearchResults, cast(object, self.row)))
                self.row = {}
                self.insideRow = False

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def do_search(self, page: int, what: str) -> None:
        parser = self.MyHtmlParser(self.url)
        page_url = f"{self.url}/s/{what}/seeders/{page}"
        retrievedHtml = retrieve_url(page_url)
        parser.feed(retrievedHtml)
        parser.close()

    def search(self, what: str, cat: str = "all") -> None:
        parser = self.MyHtmlParser(self.url)
        what = what.replace("%20", "-")
        what = what.replace(" ", "-")
        page = 1

        page_url = f"{self.url}/s/{what}/seeders/{page}"
        retrievedHtml = retrieve_url(page_url)
        pagination_matches = re.finditer(
            self.pagination_regex, retrievedHtml, re.MULTILINE
        )
        pagination_pages = [x.group() for x in pagination_matches]
        parser.feed(retrievedHtml)
        parser.close()
        if not pagination_pages:
            return
        try:
            lastPage = int(
                pagination_pages[0]
                .replace("<div>", "")
                .replace("</div>", "")
                .split(" ")[-1]
            )
        except (IndexError, ValueError):
            return
        page += 1

        jobs = [(p, what) for p in range(page, min(lastPage, MAX_PAGES) + 1)]
        _qbt_run_parallel(self.do_search, jobs, _qbt_new_deadline())
