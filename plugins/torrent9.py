# VERSION: 2.0
"""
Torrent9 (French site) search engine. The real domain changes often, so it is
fetched from a JSON file on GitHub at startup; the class-level url is an
intentional fake used for engine association. Sizes are converted from French
units (e.g. Mo) to English (MB).
"""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar

from helpers import _headers as headers
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


class torrent9:
    # Intentionally stale fake url: it only anchors engine association, the
    # real domain is resolved at startup (the site changes domains often).
    url = "http://torent9.fr"
    name = "Torrent9 (french)"
    supported_categories: ClassVar[dict[str, list[str]]] = {"all": [""]}

    def __init__(self):
        self.real_url = self.find_url()

    def find_url(self) -> str:
        """Retrieve url from github repository, so it can work even if the url change"""
        link_github = "https://raw.githubusercontent.com/menegop/qbfrench/master/urls.json"
        try:
            req = urllib.request.Request(link_github, headers=headers)
            with _qbt_safe_urlopen(req) as response:
                content = response.read().decode()
            urls = json.loads(content)
            return urls["torrent9"][0]

        except (urllib.error.URLError, ValueError, KeyError, TypeError) as errno:
            print(" ".join(("Connection error:", str(getattr(errno, "reason", errno)))))
            return "https://www.torrent9.fm"

    def download_torrent(self, desc_link: str):
        """Download file at url and write it to a file, return the path to the file and the url"""
        file, _path = tempfile.mkstemp()
        file = os.fdopen(file, "wb")
        # Download url
        req = urllib.request.Request(desc_link, headers=headers)
        try:
            with _qbt_safe_urlopen(req) as response:
                content = response.read().decode()
        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return ""
        if not content:
            return ""
        pattern = r'"btn btn-danger download" href="(\/.*?)">'

        link = self.real_url + re.findall(pattern, content)[0]
        print(link, desc_link)

    class TableRowExtractor(HTMLParser):
        def __init__(self, url: str, results: list[SearchResults]):
            self.results = results

            self.in_tr = False
            self.in_table_corps = False
            self.in_div_or_anchor = False
            self.current_row: SearchResults = {
                "link": "",
                "name": "",
                "size": "",
                "seeds": -1,
                "leech": -1,
                "engine_url": "",
            }
            self.in_name = False
            self.url = url
            self.item_counter = 0
            self.name_parts: list[str] = []
            super().__init__()

        def handle_starttag(self, tag, attrs):
            if tag == "tbody":
                # check if the table has a class of "table-corps"
                # attrs = dict(attrs)
                # if attrs.get('class') == 'table-corps':
                self.in_table_corps = True

            if self.in_table_corps and tag == "tr":
                self.in_tr = True
                self.item_counter = 0

            if self.in_tr and tag in ["td", "a"]:
                # extract the class name of the div element if it exists
                self.in_div_or_anchor = True

                if tag == "a":
                    attr_map = dict(attrs)
                    href = attr_map.get("href")
                    if href is not None:
                        self.current_row["link"] = self.url + href
                        self.current_row["desc_link"] = self.url + href

            if tag == "h3":
                self.in_name = True
                self.name_parts = []

        def handle_endtag(self, tag):
            if tag == "tr":
                if (
                    self.in_table_corps
                    and "desc_link" in self.current_row
                    and self.current_row.get("desc_link")
                    not in [res.get("desc_link") for res in self.results]
                ):
                    self.results.append(self.current_row)
                self.in_tr = False
                self.current_row = {
                    "link": "",
                    "name": "",
                    "size": "",
                    "seeds": -1,
                    "leech": -1,
                    "engine_url": "",
                }
            if tag == "tbody":
                self.in_table_corps = False
            if tag in ["td", "a"]:
                self.in_div_or_anchor = False
            if tag == "h3":
                self.in_name = False
                self.current_row["name"] = " ".join(self.name_parts)

        def handle_data(self, data):
            if self.in_div_or_anchor:
                if self.in_name:
                    self.name_parts.append(data.strip())
                else:
                    if self.item_counter == 3:
                        self.current_row["size"] = data.strip()
                    if self.item_counter == 5:
                        seeds = data.strip()
                        try:
                            self.current_row["seeds"] = int(seeds)
                        except Exception:
                            pass
                    if self.item_counter == 7:
                        leech = data.strip()
                        try:
                            self.current_row["leech"] = int(leech)
                        except Exception:
                            pass
                    self.item_counter += 1

        def get_rows(self):
            return self.results

    def search(self, what, cat="all"):
        results: list[SearchResults] = []
        len_old_result = 0
        for page in range(10):
            url = f"{self.real_url}/search_torrent/{what}/page-{page + 1}"
            try:
                data = retrieve_url(url)
                parser = self.TableRowExtractor(self.real_url, results)
                parser.feed(data)
                results = parser.results
                parser.close()
            except Exception:
                break

            if len(results) - len_old_result == 0:
                break
            len_old_result = len(results)
        # Sort results
        good_order = [
            ord_res
            for _key, ord_res in sorted(
                zip(
                    [[int(res["seeds"]), int(res["leech"])] for res in results],
                    range(len(results)),
                )
            )
        ]
        results = [results[x] for x in good_order[::-1]]

        # Fix size and add engine
        for res in results:
            res["size"] = unit_fr2en(str(res["size"]))
            res["engine_url"] = self.url
        # Print
        for res in results:
            _qbt_prettyPrinter(res)


def unit_fr2en(size: str) -> str:
    """Convert french size unit to english"""
    return re.sub(r"([KMGTP])o", lambda match: match.group(1) + "B", size, flags=re.IGNORECASE)


# For testing
# if __name__ == "__main__":
#    engine = torrent9()
