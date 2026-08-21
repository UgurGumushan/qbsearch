# VERSION: 1.3
"""
YourBittorrent (https://yourbittorrent.com) search engine. Scrapes the
results table; because the site's page navigation is broken, only the first
50 results can be retrieved per query.
"""

import re
import urllib.parse
from typing import ClassVar

from helpers import download_file
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


# Raised when a torrent page is missing its .torrent download link.
class ParseError(Exception):
    pass


class yourbittorrent:
    url = "https://yourbittorrent.com/"
    name = "YourBittorrent"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "1",
        "tv": "3",
        "music": "2",
        "games": "4",
        "anime": "6",
        "software": "5",
    }

    # The site's page navigation is broken, so only the first 50 results of a
    # query can be retrieved; the query itself is the only selector.

    class HTMLParser:
        def __init__(self, url: str):
            self.url = url
            self.noTorrents = False

        def feed(self, html: str):
            self.noTorrents = False
            torrents: list[tuple[str, str, str, str, str]] = self.__findTorrents(html)
            resultSize = len(torrents)
            if resultSize == 0:
                self.noTorrents = True
                return
            for torrent in range(resultSize):
                data: SearchResults = {
                    "link": torrents[torrent][0],
                    "name": torrents[torrent][1],
                    "size": torrents[torrent][2],
                    "seeds": int(torrents[torrent][3].replace(",", "")),
                    "leech": int(torrents[torrent][4].replace(",", "")),
                    "engine_url": self.url,
                    "desc_link": urllib.parse.unquote(torrents[torrent][0]),
                }
                _qbt_prettyPrinter(data)

        def __findTorrents(self, html: str) -> list[tuple[str, str, str, str, str]]:
            torrents: list[tuple[str, str, str, str, str]] = []
            current_table = re.search(
                r'<table[^>]*class="[^"]*\byb-rows\b[^"]*"[^>]*>.+?</table>',
                html,
            )
            if current_table:
                trs = re.findall(r"<tr(?:\s[^>]*)?>.+?</tr>", current_table.group(0))
                for tr in trs:
                    anchor = re.search(
                        r'<a[^>]*class="yb-tname"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        tr,
                    )
                    size = re.search(
                        r'data-label="Size"[^>]*>.*?<a[^>]*>([^<]+)</a>', tr
                    )
                    seeds = re.search(
                        r'data-label="Seed"[^>]*>.*?class="sd">([0-9,]+)', tr
                    )
                    leech = re.search(
                        r'data-label="Peers"[^>]*>.*?class="pr">([0-9,]+)', tr
                    )
                    if anchor is None or size is None or seeds is None or leech is None:
                        continue
                    name = re.sub(r"<[^>]+>", "", anchor.group(2)).strip()
                    link = urllib.parse.urljoin(self.url, anchor.group(1))
                    torrents.append(
                        (
                            link,
                            name,
                            size.group(1),
                            seeds.group(1),
                            leech.group(1),
                        )
                    )
                return torrents

            legacy_tables = re.findall(r"<div class=\"table-responsive\">.+?</table></div>", html)
            if not legacy_tables:
                return torrents
            html = legacy_tables[-1]
            trs = re.findall(r"<tr class=\"table-default\">.+?</tr>", html)
            for tr in trs:
                # Extract from the A node all the needed information
                url_titles = re.search(
                    r".+?href=\"(.+?)\".+?title=\"(.+?)\".+?([0-9\.\,]+ (TB|GB|MB|kB)).+?sd\">([0-9,]+)<.+?pr\">([0-9,]+)<",
                    tr,
                )
                if url_titles:
                    torrents.append(
                        (
                            urllib.parse.quote(f"{self.url}{url_titles.group(1)}"),
                            url_titles.group(2)
                            .replace("<b>", "")
                            .replace("</b>", "")
                            .replace("<span style=color:#39a8bb>", "")
                            .replace("</span>", ""),
                            url_titles.group(3).replace(",", ""),
                            url_titles.group(5).replace(",", ""),
                            url_titles.group(6).replace(",", ""),
                        )
                    )
            return torrents

    def download_torrent(self, info: str) -> None:
        torrent_page: str = retrieve_url(urllib.parse.unquote(info))
        file_link = re.search(r"(down/.+?\.torrent)", torrent_page)
        if file_link and file_link.groups():
            print(download_file(self.url + file_link.groups()[0]))
        else:
            raise ParseError("Error, please fill a bug report!")

    def search(self, what: str, cat: str = "all") -> None:
        what = what.replace("%20", "-")
        parser = self.HTMLParser(self.url)
        category = "" if cat == "all" else f"&c={self.supported_categories[cat]}"
        url = f"{self.url}?q={what}{category}"
        # Some replacements to format the html source
        html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
        parser.feed(html)
